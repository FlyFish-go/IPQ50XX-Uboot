#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Self-test of make_rules.py / make_pack.py --auto with synthetic images.

    python3 -I tools/bootbridge2/pack/test_make_rules.py

A board image must be the normalized APPSBL MBN for the flash link address
with exactly one NAND-auto identity of that board. A RAM rescue ELF renamed
to .mbn, a truncated or patched MBN, a second identity or another board's
identity must stop the generator before a rule file exists. --hold must drop
the candidates of a NAND profile but keep its nand rule.
"""
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "release-tools"))
import appsbl_packager as ap  # noqa: E402

FLASH = 0x4A920000
RAM = 0x49A20000
PART = 0x140000
fails = 0


def check(cond, what):
    global fails
    print(("ok   " if cond else "FAIL ") + what)
    fails += not cond


def elf(entry, payload):
    """Minimal stripped ARM ELF32 with one LOAD and one GNU_STACK header."""
    off = 52 + 2 * 32
    hdr = b"\x7fELF\x01\x01\x01" + b"\0" * 9 + struct.pack(
        "<HHIIIIIHHHHHH", 2, 40, 1, entry, 52, 0, 0x5000200, 52, 32, 2, 40, 0, 0)
    load = struct.pack("<8I", 1, off, entry, entry, len(payload), len(payload), 7, 1)
    stack = struct.pack("<8I", 0x6474E551, 0, 0, 0, 0, 0, 7, 0x10)
    return hdr + load + stack + payload


def ident(board):
    return b"H3C-UBOOT-ID:v1;board=" + board.encode() + b";profile=auto;mask=none;ecc=none;\0"


def mbn(board, extra=b""):
    return ap.package_elf(elf(FLASH, b"\x01" * 0x4000 + ident(board) + extra + b"\x02" * 64))


def run(script, *args):
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def setup(d, images):
    profiles = {"profiles": [
        {"profile_id": "h3c-oem-efba-128m-2k-sp64", "oem_model": "W25N01GWZEIG",
         "manufacturer_id": 0xef, "chip_id": 0xba, "capacity_mib": 128, "page_bytes": 2048,
         "erase_bytes": 131072, "raw_spare_bytes": 64},
        {"profile_id": "h3c-oem-a1a5-128m-2k-sp64-p2048-e131072", "oem_model": "FM25LS01",
         "manufacturer_id": 0xa1, "chip_id": 0xa5, "capacity_mib": 128, "page_bytes": 2048,
         "erase_bytes": 131072, "raw_spare_bytes": 64}]}
    cands = {"release": "uboot-test", "candidates": [
        {"board": b, "nand_profile_id": p, "load_ecc_bits": 4, "storage_ecc_bits": 4,
         "folder": f"HW-{b}/x-ECC4", "appsbl_partition_bytes": PART}
        for b in "ABCD" for p in ("h3c-oem-efba-128m-2k-sp64",
                                  "h3c-oem-a1a5-128m-2k-sp64-p2048-e131072")]}
    json.dump(profiles, open(os.path.join(d, "profiles.json"), "w"))
    json.dump(cands, open(os.path.join(d, "cands.json"), "w"))
    img = os.path.join(d, "img")
    os.makedirs(img, exist_ok=True)
    for b in "ABCD":
        open(os.path.join(img, f"h3c-hw-{b.lower()}.mbn"), "wb").write(images.get(b, mbn(b)))
    return ["--candidates", os.path.join(d, "cands.json"),
            "--nand-profiles", os.path.join(d, "profiles.json"),
            "--set", "BB2-TEST", "--auto", img]


def main():
    good = mbn("A")
    ap.verify_mbn(good)
    check(True, "verify_mbn accepts what package_elf makes")
    for name, bad in (("RAM ELF", elf(RAM, b"\x01" * 0x4000 + ident("A"))),
                      ("flash ELF before packaging", elf(FLASH, b"\x01" * 0x4000 + ident("A"))),
                      ("truncated MBN", good[:-16]),
                      ("payload byte changed", good[:-1] + bytes([good[-1] ^ 1]))):
        try:
            ap.verify_mbn(bad)
            check(False, f"verify_mbn refuses {name}")
        except ap.PackError:
            check(True, f"verify_mbn refuses {name}")

    # SDRAM window: a LOAD of exactly 0xe0000 bytes ends at 0x4aa00000 and fits;
    # one byte more must be refused by both the packager and the verifier.
    limit = ap.SDRAM_END - FLASH
    edge = ap.package_elf(elf(FLASH, ident("A") + b"\x03" * (limit - len(ident("A")))))
    try:
        ap.verify_mbn(edge)
        check(True, "LOAD of 0xe0000 bytes accepted")
    except ap.PackError as e:
        check(False, f"LOAD of 0xe0000 bytes accepted ({e})")
    over_elf = elf(FLASH, ident("A") + b"\x03" * (limit + 1 - len(ident("A"))))
    try:
        ap.package_elf(over_elf)
        check(False, "package_elf refuses a LOAD of 0xe0001 bytes")
    except ap.PackError:
        check(True, "package_elf refuses a LOAD of 0xe0001 bytes")
    saved = ap.SDRAM_END
    ap.SDRAM_END = saved + 0x1000	# build the oversize MBN the packager would refuse
    try:
        over = ap.package_elf(over_elf)
    finally:
        ap.SDRAM_END = saved
    try:
        ap.verify_mbn(over)
        check(False, "verify_mbn refuses a LOAD of 0xe0001 bytes")
    except ap.PackError:
        check(True, "verify_mbn refuses a LOAD of 0xe0001 bytes")

    with tempfile.TemporaryDirectory() as d:
        args = setup(d, {})
        rc, out, err = run("make_rules.py", *args)
        cands = [l for l in out.splitlines() if l.startswith("candidate ")]
        check(rc == 0 and len(cands) == 8, f"good images: 8 candidates (rc {rc} {err.strip()})")
        check(all("file=candidates/h3c-hw-" in l for l in cands), "candidates point at h3c-hw-<x>.mbn")
        rules = os.path.join(d, "rules.txt")
        open(rules, "w").write(out)
        rc, _, err = run("make_pack.py", "--rules", rules, "--auto", args[-1],
                         "-o", os.path.join(d, "p.bbpack"))
        check(rc == 0, f"make_pack stores the 4 images ({err.strip()})")

        rc, out, err = run("make_rules.py", *args,
                           "--hold", "h3c-oem-a1a5-128m-2k-sp64-p2048-e131072=untested")
        cands = [l for l in out.splitlines() if l.startswith("candidate ")]
        check(rc == 0 and len(cands) == 4 and "a1a5" not in "".join(cands),
              "--hold drops the held profile's candidates")
        check("nand h3c-oem-a1a5-128m-2k-sp64-p2048-e131072 " in out,
              "--hold keeps the held profile's nand rule")

    bad_sets = {
        "RAM rescue ELF named h3c-hw-b.mbn": {"B": elf(RAM, b"\x01" * 0x4000 + ident("B"))},
        "truncated h3c-hw-c.mbn": {"C": mbn("C")[:-100]},
        "two identities": {"D": mbn("D", ident("D"))},
        "HW-A identity in h3c-hw-b.mbn": {"B": mbn("A")},
    }
    for what, images in bad_sets.items():
        with tempfile.TemporaryDirectory() as d:
            rc, out, err = run("make_rules.py", *setup(d, images))
            check(rc != 0 and "candidate " not in out, f"refused: {what} ({err.strip()})")

    print("make_rules self-test:", "PASS" if not fails else f"{fails} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
