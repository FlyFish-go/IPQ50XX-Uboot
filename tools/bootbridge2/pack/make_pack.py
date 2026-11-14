#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build a BootBridge v2 rule pack (format: runtime/pack.h).

    make_pack.py --rules rules.txt --dist DIR --candidates CANDIDATES.json -o rules.bbpack
    make_pack.py --rules rules.txt --auto DIR -o rules.bbpack

Every `candidate` line of the rule file must have its file in DIR: the
extracted per-NAND U-Boot release (HW-<board>/<model>-ECC<n>/appsbl.mbn), or
with --auto the folder of h3c-hw-<x>.mbn. Candidates that share a file are
stored once. Output is deterministic: same inputs, same bytes.
"""
import argparse
import hashlib
import io
import json
import lzma
import os
import struct
import sys
import tarfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "release-tools"))
import appsbl_packager  # noqa: E402

LZMA_FILTERS = [{"id": lzma.FILTER_LZMA1, "preset": 9 | lzma.PRESET_EXTREME,
                 "dict_size": 2 << 20}]	# runtime decoder budget: 2 MiB dictionary


def candidate_lines(rules):
    for line in rules.splitlines():
        tok = line.split("#", 1)[0].split()
        if tok and tok[0] == "candidate":
            yield tok[1], dict(t.split("=", 1) for t in tok[2:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True)
    ap.add_argument("--dist")
    ap.add_argument("--candidates", help="CANDIDATES.json of the release (with --dist)")
    ap.add_argument("--auto", help="folder with h3c-hw-<x>.mbn")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    if bool(a.auto) == bool(a.dist) or (a.dist and not a.candidates):
        sys.exit("give either --auto DIR, or --dist DIR with --candidates")

    rules = open(a.rules, "rb").read()
    folders = {}
    if a.dist:
        for c in json.load(open(a.candidates))["candidates"]:
            cid = f"{c['board']}-{c['nand_profile_id']}-ecc{c['storage_ecc_bits']}"
            folders[cid] = c["folder"]

    stored = {}	# file -> (bytes, sha256) already in the archive
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for cid, kv in sorted(candidate_lines(rules.decode())):
            if kv["file"] in stored:
                if stored[kv["file"]] != (kv["bytes"], kv["sha256"]):
                    sys.exit(f"{cid}: {kv['file']} listed with two different payloads")
                continue
            if a.auto:
                name = os.path.basename(kv["file"])
                if not (name.startswith("h3c-hw-") and name.endswith(".mbn")):
                    sys.exit(f"{cid}: {kv['file']} is not an h3c-hw-<x>.mbn")
                path = os.path.join(a.auto, name)
            else:
                path = os.path.join(a.dist, folders[cid], "appsbl.mbn")
            data = open(path, "rb").read()
            if a.auto:
                try:
                    appsbl_packager.verify_mbn(data)
                except appsbl_packager.PackError as e:
                    sys.exit(f"{cid}: {name}: {e}")
            if len(data) != int(kv["bytes"]) or hashlib.sha256(data).hexdigest() != kv["sha256"]:
                sys.exit(f"{cid}: payload differs from the rule file")
            stored[kv["file"]] = (kv["bytes"], kv["sha256"])
            info = tarfile.TarInfo(kv["file"])
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    tar_bytes = tar_buf.getvalue()
    packed = lzma.compress(tar_bytes, format=lzma.FORMAT_ALONE, filters=LZMA_FILTERS)

    digest = hashlib.sha256(rules + packed).digest()
    header = b"BBPK" + struct.pack("<IIII", 1, len(rules), len(packed), len(tar_bytes)) + \
        digest + b"\0" * 12
    assert len(header) == 64
    with open(a.output, "wb") as f:
        f.write(header + rules + packed)
    print(f"{a.output}: {64 + len(rules) + len(packed)} bytes, rules {len(rules)}, "
          f"lzma {len(packed)}, tar {len(tar_bytes)}", file=sys.stderr)


if __name__ == "__main__":
    main()
