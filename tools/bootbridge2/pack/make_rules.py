#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Generate a BootBridge v2 rule file from a U-Boot release.

    make_rules.py --candidates CANDIDATES.json --nand-profiles nand_profiles.json \
                  --set BB2-R1 [--dist DIR] > rules.txt
    make_rules.py --candidates CANDIDATES.json --nand-profiles nand_profiles.json \
                  --set BB2-R4 --auto DIR [--release v0.2.0] > rules.txt

CANDIDATES.json comes from the U-Boot release (uboot-v0.1.0-pre.3 and later).
The NAND profile list is the U-Boot NAND catalog in JSON form. With --dist,
every candidate's appsbl.mbn is checked against the recorded size and hash.

With --auto (U-Boot v0.2.0 and later) DIR holds one NAND-auto image per board,
h3c-hw-<x>.mbn, which finds the NAND profile and ECC itself at boot. The
CANDIDATES.json of the last per-NAND release still decides which board, NAND
and ECC combinations are accepted (a chip outside it is refused as before);
every accepted combination of a board installs that board's one image.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import struct

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "release-tools"))
import appsbl_packager  # noqa: E402  (MBN contract shared with the U-Boot release)

# Board groups. A and C have their own OEM boot routes. HW-B and HW-D share
# mp02.1 / machid 0x08040000; only HW-D boards carry a 5 GHz FEM, which shows
# in the factory calibration block (ART + 0x26800): +0x3a 0x60/0x50 and
# +0x45 0x09/0x01. A FEM-less HW-D (RC3000 B0) therefore gets the HW-B build,
# which was bench-verified to run on HW-D.
BOARD_RULES = """\
board A layout=nx30 route=mp03.1 machid=0x08040001
board C layout=nx30 route=mp03.1-c2 machid=0x08040101
board D layout=nx30 route=mp02.1 machid=0x08040000 art5g@0=01000404 art5g@3a=60 art5g@45=09
board B layout=nx30 route=mp02.1 machid=0x08040000 art5g@0=01000404 art5g@3a=50 art5g@45=01
"""

NX54_SBL1 = "36e919527fb80dd70607ebfd965172b40b880845d02dc581b8444c4c7b3f88cf"
# NX54 NAND/ECC combinations come from the stock NX54 tables, the same way as
# the NX30 family: the stock NX54 APPSBL NAND table (18 rows) is byte-identical
# to the NX30 OEM tables A1 and B, and the NX54V100R014 kernel NAND ID rows
# (17 rows, OOB and ECC strength) equal the NX30 R012 kernel rows. The
# combinations below are exactly what the B table plus that kernel accept
# (nand_schema.runtime_profiles(["B"])); test_make_rules.py checks this.
NX54_NANDS = [
    ("h3c-oem-2c15-128m-2k-sp128", 8),
    ("h3c-oem-98d2-128m-2k-sp128", 8),
    ("h3c-oem-98db-128m-2k-sp64", 4),
    ("h3c-oem-a1a5-128m-2k-sp128-p2048-e131072", 8),
    ("h3c-oem-c292-128m-2k-sp64", 4),
    ("h3c-oem-c811-128m-2k-sp64", 4),
    ("h3c-oem-c821-128m-2k-sp64", 4),
    ("h3c-oem-c822-256m-2k-sp64", 4),
    ("h3c-oem-c841-128m-2k-sp128", 8),
    ("h3c-oem-c845-128m-2k-sp128", 4),
    ("h3c-oem-c8c1-128m-2k-sp128", 8),
    ("h3c-oem-c8c9-128m-2k-sp64", 4),
    ("h3c-oem-e572-128m-2k-sp64", 4),
    ("h3c-oem-e5a4-128m-2k-sp128", 8),
    ("h3c-oem-efba-128m-2k-sp64", 4),
    ("h3c-oem-efbc-128m-2k-sp64", 4),
    ("h3c-oem-efbf-256m-2k-sp64", 4),
]


def nx54_rules(dist, profiles):
    name = "h3c-nx54.mbn"
    data = open(os.path.join(dist, name), "rb").read()
    try:
        appsbl_packager.verify_mbn(data)
    except appsbl_packager.PackError as e:
        sys.exit(f"{name}: {e}")
    ident = b"H3C-UBOOT-ID:v1;board=NX54;profile=auto;mask=none;ecc=none;\0"
    if data.count(b"H3C-UBOOT-ID:v1;") != 1 or data.count(ident) != 1:
        sys.exit(f"{name}: not exactly one NX54 NAND-auto identity")
    part_bytes = 0x140000
    if len(data) > part_bytes:
        sys.exit(f"{name}: larger than APPSBL")
    padded = data + b"\xff" * (part_bytes - len(data))
    out = [f"board NX54 layout=nx54 route=mp03.1 machid=0x08040001 product=NX54 sbl1.sha256={NX54_SBL1}"]
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "u-boot-2016", "include", "h3c_nand_catalog.h")
    catalog = open(catalog_path, encoding="utf-8").read()
    pattern = r'\{"([^" ]+)","[^"]*","[^"]*",\{0x([0-9a-f]+),0x([0-9a-f]+)\},([^}]+)\}'
    found = set()
    for profile, mfr, chip, numbers in re.findall(pattern, catalog):
        vals = [int(x.strip().rstrip("Uu"), 0) for x in numbers.split(",")]
        if len(vals) != 20:
            sys.exit("invalid NAND catalog row " + profile)
        # Verify a compiled catalog row, including its pointer to this profile,
        # ID and geometry, in the hash-verified target MBN's LOAD segment.
        profile_name = profile.encode() + b"\0"
        pos = data.find(profile_name, appsbl_packager.LOAD_OFFSET)
        if pos < 0:
            continue
        address = appsbl_packager.LOAD_ADDRESS + pos - appsbl_packager.LOAD_OFFSET
        row = (re.escape(struct.pack("<I", address)) + b".{8}" +
               re.escape(bytes((int(mfr, 16), int(chip, 16))) + b"\0\0" +
                         struct.pack("<5I", *vals[:5])))
        if not re.search(row, data[appsbl_packager.LOAD_OFFSET:], re.DOTALL):
            continue
        # Only entries with QPIC ID, geometry and fixed-read support.
        if vals[19] & 0x1c != 0x1c:
            continue
        for ecc, bit, oob in ((4, 1, vals[14]), (8, 2, vals[14])):
            if vals[16] & bit and oob:
                found.add((mfr, chip, ecc, oob, vals[14]))
    if not found:
        sys.exit("no target MBN NAND catalog entries found")
    for pid, ecc in NX54_NANDS:
        p = profiles.get(pid)
        if p is None:
            sys.exit(f"NX54 NAND profile missing: {pid}")
        key = ("%02x" % p["manufacturer_id"], "%02x" % p["chip_id"], ecc)
        if not any(f[:3] == key for f in found):
            sys.exit(f"NX54 MBN NAND catalog lacks {pid} ECC{ecc}")
    for pid, ecc in NX54_NANDS:
        out.append(f"candidate NX54-auto-{pid}-ecc{ecc} board=NX54 nand={pid} ecc={ecc} "
                   f"bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()} "
                   f"part_bytes={part_bytes} part_sha256={hashlib.sha256(padded).hexdigest()} "
                   f"file=candidates/{name}")
    return out


def nand_rule(p):
    models = []
    for m in [p["oem_model"]] + p.get("model_aliases", []):
        if m not in models:
            models.append(m)
    for m in models:
        if not re.fullmatch(r"[A-Za-z0-9()._-]+", m):
            sys.exit(f"unsafe model name {m!r}")
    return (f"nand {p['profile_id']} nand.id={p['manufacturer_id']:02x}:{p['chip_id']:02x} "
            f"nand.model={'|'.join(models)} nand.mib={p['capacity_mib']} "
            f"nand.page={p['page_bytes']} nand.erase_kib={p['erase_bytes'] // 1024} "
            f"nand.oob={p['raw_spare_bytes']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--nand-profiles", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--dist", help="extracted release folders HW-<board>/<model>-ECC<n>/")
    ap.add_argument("--auto", help="folder with the per-board NAND-auto images h3c-hw-<x>.mbn")
    ap.add_argument("--release", default="", help="U-Boot release of the --auto images, for the header")
    ap.add_argument("--nx54", action="store_true", help="also read h3c-nx54.mbn from --auto DIR")
    ap.add_argument("--hold", action="append", default=[], metavar="PROFILE=REASON",
                    help="--auto only: write no candidate for this NAND profile, so the bridge "
                         "refuses it before writing (its nand rule stays, so it cannot be "
                         "mistaken for another profile)")
    a = ap.parse_args()
    if a.auto and a.dist:
        sys.exit("--auto and --dist exclude each other")
    if a.nx54 and not a.auto:
        sys.exit("--nx54 needs --auto DIR")
    if a.hold and not a.auto:
        sys.exit("--hold needs --auto")
    held = {}
    for h in a.hold:
        pid, _, why = h.partition("=")
        if not why or not re.fullmatch(r"h3c-oem-[a-z0-9-]+", pid) or "\n" in why:
            sys.exit(f"--hold wants PROFILE=REASON, got {h!r}")
        held[pid] = why

    cands = json.load(open(a.candidates))
    profiles = {p["profile_id"]: p for p in json.load(open(a.nand_profiles))["profiles"]}

    if a.auto:
        origin = f"# U-Boot {a.release or '?'}: one NAND-auto image per board; " \
                 f"accepted NAND/ECC from {cands.get('release', '?')}"
    else:
        origin = f"# from {cands.get('release', '?')} source {cands.get('source_commit', '?')}"
    out = ["bbrules 1", f"set {a.set}", origin, "", BOARD_RULES]
    used = sorted({c["nand_profile_id"] for c in cands["candidates"]})
    if a.nx54:
        used = sorted(set(used) | {pid for pid, _ in NX54_NANDS})
    missing = [u for u in used if u not in profiles]
    if missing:
        sys.exit(f"candidates use unknown NAND profiles: {missing}")
    out += [nand_rule(profiles[u]) for u in used] + [""]
    unknown = [h for h in held if h not in used]
    if unknown:
        sys.exit(f"--hold names profiles no candidate uses: {unknown}")
    out += [f"# held, no candidate: {pid} ({why})" for pid, why in sorted(held.items())]
    if held:
        out.append("")

    auto = {}	# board -> (bytes, sha256, part_sha256, file)
    seen = set()
    for c in sorted(cands["candidates"], key=lambda c: (c["board"], c["nand_profile_id"],
                                                         c["storage_ecc_bits"])):
        if c["load_ecc_bits"] != c["storage_ecc_bits"]:
            sys.exit(f"{c['folder']}: load/store ECC differ, not supported")
        key = (c["board"], c["nand_profile_id"], c["storage_ecc_bits"])
        if key in seen:
            sys.exit(f"duplicate candidate {key}")
        seen.add(key)
        if a.auto:
            b = c["board"]
            if c["nand_profile_id"] in held:
                continue
            if b not in auto:
                name = f"h3c-hw-{b.lower()}.mbn"
                data = open(os.path.join(a.auto, name), "rb").read()
                # The whole MBN must be the normalized APPSBL container for the
                # flash link address: a RAM rescue ELF, a truncated file or a
                # stale hash is refused here, before any hash is trusted.
                try:
                    appsbl_packager.verify_mbn(data)
                except appsbl_packager.PackError as e:
                    sys.exit(f"{name}: {e}")
                ident = b"H3C-UBOOT-ID:v1;board=" + b.encode() + \
                    b";profile=auto;mask=none;ecc=none;\0"
                if data.count(b"H3C-UBOOT-ID:v1;") != 1 or data.count(ident) != 1:
                    sys.exit(f"{name}: not exactly one NAND-auto identity for HW-{b}")
                if len(data) > c["appsbl_partition_bytes"]:
                    sys.exit(f"{name}: larger than the APPSBL partition")
                part = data + b"\xff" * (c["appsbl_partition_bytes"] - len(data))
                auto[b] = (len(data), hashlib.sha256(data).hexdigest(),
                           hashlib.sha256(part).hexdigest(), f"candidates/{name}")
            size, sha, part_sha, path = auto[b]
            cid = f"HW-{b}-auto-{c['nand_profile_id']}-ecc{c['storage_ecc_bits']}"
            out.append(f"candidate {cid} board={b} nand={c['nand_profile_id']} "
                       f"ecc={c['storage_ecc_bits']} bytes={size} sha256={sha} "
                       f"part_bytes={c['appsbl_partition_bytes']} part_sha256={part_sha} "
                       f"file={path}")
            continue
        cid = f"{c['board']}-{c['nand_profile_id']}-ecc{c['storage_ecc_bits']}"
        if a.dist:
            path = os.path.join(a.dist, c["folder"], "appsbl.mbn")
            data = open(path, "rb").read()
            if len(data) != c["appsbl_mbn_bytes"] or \
                    hashlib.sha256(data).hexdigest() != c["appsbl_mbn_sha256"]:
                sys.exit(f"{path}: size or hash differs from CANDIDATES.json")
            part = data + b"\xff" * (c["appsbl_partition_bytes"] - len(data))
            if hashlib.sha256(part).hexdigest() != c["appsbl_partition_sha256"]:
                sys.exit(f"{path}: 0xff-padded partition hash differs from CANDIDATES.json")
        out.append(f"candidate {cid} board={c['board']} nand={c['nand_profile_id']} "
                   f"ecc={c['storage_ecc_bits']} bytes={c['appsbl_mbn_bytes']} "
                   f"sha256={c['appsbl_mbn_sha256']} part_bytes={c['appsbl_partition_bytes']} "
                   f"part_sha256={c['appsbl_partition_sha256']} file=candidates/{cid}.mbn")
    if a.nx54:
        if any(pid in held for pid, _ in NX54_NANDS):
            sys.exit("an NX54 NAND profile is held; refusing to emit NX54 candidates")
        out += [""] + nx54_rules(a.auto, profiles)
    print("\n".join(out))


if __name__ == "__main__":
    main()
