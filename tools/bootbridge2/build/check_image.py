#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Independent structural check of a finished bridge image.

    check_image.py --image bridge.bin --official original.bin [--pack rules.bbpack]

Re-parses the image from scratch: H3C header word sum, FIT hashes over the
UBI data, UBI headers and volume table, the SquashFS root and, with --pack,
that the pack sits right after the SquashFS at a LEB boundary.
"""
import argparse
import hashlib
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_fit  # noqa: E402
import vendor_ubi  # noqa: E402
import bridge_kernel  # noqa: E402
import build_bridge  # noqa: E402


def fail(msg):
    sys.exit("FAIL: " + msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--official", required=True)
    ap.add_argument("--pack")
    a = ap.parse_args()
    img = open(a.image, "rb").read()
    off = open(a.official, "rb").read()
    official_sha = hashlib.sha256(off).hexdigest()
    if official_sha not in bridge_kernel.SOURCES:
        fail("unreviewed official source")
    profile = bridge_kernel.source_profile(official_sha)
    header = build_bridge.header_template(off, profile)

    if len(img) < 200 or len(img) % 4:
        fail("H3C length/alignment")
    if sum(v[0] for v in struct.iter_unpack(">I", img[64:])) & 0xffffffff != 0xffffffff:
        fail("H3C word sum")
    if img[:68] != header[:68] or img[76:80] != header[76:80] or img[84:160] != header[84:160]:
        fail("H3C header fields other than sizes/checksum differ from the official image")
    fit_len = struct.unpack_from(">I", img, 164)[0]
    tail = -fit_len % 4 + profile["zero_tail_bytes"]
    if fit_len < 40 or len(img) != 160 + fit_len + tail or any(img[160 + fit_len:]):
        fail("FIT length")
    if struct.unpack_from(">I", img, 68)[0] != len(img) - 64 or \
            struct.unpack_from(">I", img, 80)[0] != len(img) - 160:
        fail("H3C payload sizes")
    nodes = vendor_fit.fdt_props(img[160:160 + fit_len])
    imgs = [n for n in nodes if n.startswith("/images/") and n.count("/") == 2]
    if len(imgs) != 1 or not imgs[0].startswith("/images/ubi-"):
        fail("FIT must hold exactly one ubi image and no bootloader")
    ubi = nodes[imgs[0]]["data"]
    crc = nodes[imgs[0] + "/hash@1"]["value"]
    sha1 = nodes[imgs[0] + "/hash@2"]["value"]
    if crc != struct.pack(">I", zlib.crc32(ubi) & 0xffffffff) or sha1 != hashlib.sha1(ubi).digest():
        fail("FIT hash values")
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "b.ubi"
        p.write_bytes(ubi)
        meta, streams, _, _ = vendor_ubi.parse(p)
        if len(ubi) > profile["slot_bytes"]:
            fail("UBI exceeds system slot")
        # Independently extract the source and reproduce only its reviewed DT
        # edits: a structurally valid UBI with a wrong kernel must also fail.
        p.write_bytes(build_bridge.split_official(off))
        stock_meta, stock, _, _ = vendor_ubi.parse(p)
        expected, _ = bridge_kernel.transform_kernel(stock["kernel"], official_sha)
        if streams["kernel"] != expected or meta["volume_table"] != stock_meta["volume_table"]:
            fail("kernel or OEM volume table differs")
        if any(streams[n] != stock[n] for n in ("wifi_fw", "bt_fw")):
            fail("OEM firmware volumes differ")
        rootfs = streams["ubi_rootfs"]
        if rootfs[:4] != b"hsqs":
            fail("ubi_rootfs is not SquashFS")
        used = struct.unpack_from("<Q", rootfs, 40)[0]
        (Path(t) / "r.sqfs").write_bytes(rootfs[:used])
        listing = subprocess.run(["unsquashfs", "-l", str(Path(t) / "r.sqfs")], capture_output=True,
                                 text=True)
        if listing.returncode or "squashfs-root/usr/sbin/bbd" not in listing.stdout:
            fail("SquashFS listing lacks /usr/sbin/bbd")
        pack_at = -(-used // vendor_ubi.LEB) * vendor_ubi.LEB
        if a.pack:
            pack = open(a.pack, "rb").read()
            if rootfs[pack_at:pack_at + len(pack)] != pack:
                fail("pack not found right after the SquashFS")
        elif rootfs[pack_at:pack_at + 4] == b"BBPK":
            fail("base image unexpectedly carries a pack")
    print(f"OK {a.image}: {len(img)} bytes, volumes "
          f"{[v['name'] for v in meta['volume_table']]}, squashfs {used} bytes, pack at {pack_at}, "
          f"FIT {fit_len} bytes, zero tail {tail} bytes")


if __name__ == "__main__":
    main()
