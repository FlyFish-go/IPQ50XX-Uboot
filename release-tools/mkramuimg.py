#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Wrap a RAM-linked U-Boot ELF in a legacy uImage so a stock U-Boot can run it.

The stock QSDK U-Boot maps RAM execute-never, so `go` and `bootelf` do not
work; `bootm` does (it hands over like a kernel). The uImage is a plain Linux
ARM image whose load address and entry point are the ELF's, and bootm passes
the device tree given on its command line in r2.

Trial run, nothing is written to flash (type these in the stock U-Boot):

    printenv fdtcontroladdr              # note the address
    tftpboot 0x44000000 <board>-ram.uimg
    bootm 0x44000000 - <fdtcontroladdr>

Build the ELF with CONFIG_RAM_TRIAL_BUILD=y (text base 0x49A20000, clear of
the stock U-Boot at 0x4A920000). release-tools/ci-build.sh does both steps.

usage: mkramuimg.py <ram.elf> <out.uimg> [--name NAME] [--load 0x49A20000]
"""
import argparse
import os
import struct
import sys
import zlib

IH_MAGIC = 0x27051956
IH_OS_LINUX, IH_ARCH_ARM, IH_TYPE_KERNEL, IH_COMP_NONE = 5, 2, 2, 0
PT_LOAD = 1
EM_ARM = 40
RAM_TEXT_BASE = 0x49A20000


class ImageError(Exception):
    pass


def elf_payload(elf: bytes):
    """Return (load_address, entry, bytes) of the single file-backed PT_LOAD."""
    if len(elf) < 52 or elf[:4] != b"\x7fELF" or elf[4] != 1 or elf[5] != 1:
        raise ImageError("not a little-endian ELF32 file")
    e_type, e_machine = struct.unpack_from("<HH", elf, 16)
    entry, phoff = struct.unpack_from("<II", elf, 24)
    phentsize, phnum = struct.unpack_from("<HH", elf, 42)
    if e_machine != EM_ARM:
        raise ImageError("not an ARM ELF")
    loads = []
    for i in range(phnum):
        p_type, off, vaddr, paddr, filesz, memsz = struct.unpack_from("<6I", elf, phoff + i * phentsize)
        if p_type == PT_LOAD and filesz:
            loads.append((off, vaddr, filesz))
    if len(loads) != 1:
        raise ImageError(f"expected one file-backed LOAD segment, found {len(loads)}")
    off, vaddr, filesz = loads[0]
    if off + filesz > len(elf):
        raise ImageError("LOAD segment runs past the end of the file")
    if not vaddr <= entry < vaddr + filesz:
        raise ImageError("entry point is outside the LOAD segment")
    return vaddr, entry, elf[off:off + filesz]


def make_uimage(elf: bytes, name: str, expect_load: int = RAM_TEXT_BASE, timestamp: int = 0) -> bytes:
    load, entry, body = elf_payload(elf)
    if expect_load is not None and load != expect_load:
        raise ImageError(f"ELF is linked at 0x{load:x}, expected 0x{expect_load:x}"
                         " (build with CONFIG_RAM_TRIAL_BUILD=y)")
    raw_name = name.encode()[:31].ljust(32, b"\0")

    def header(hcrc):
        return struct.pack(">7I4B", IH_MAGIC, hcrc, timestamp, len(body), load, entry,
                           zlib.crc32(body) & 0xFFFFFFFF,
                           IH_OS_LINUX, IH_ARCH_ARM, IH_TYPE_KERNEL, IH_COMP_NONE) + raw_name

    return header(zlib.crc32(header(0)) & 0xFFFFFFFF) + body


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("elf")
    ap.add_argument("out")
    ap.add_argument("--name", help="image name, 31 bytes at most (default: output file name)")
    ap.add_argument("--load", type=lambda s: int(s, 0), default=RAM_TEXT_BASE,
                    help="load address the ELF must be linked at (default 0x%X)" % RAM_TEXT_BASE)
    args = ap.parse_args(argv)
    name = args.name or os.path.basename(args.out).rsplit(".", 1)[0]
    try:
        with open(args.elf, "rb") as f:
            img = make_uimage(f.read(), name, args.load, int(os.environ.get("SOURCE_DATE_EPOCH", "0")))
    except (OSError, ImageError) as e:
        print(f"mkramuimg: {e}", file=sys.stderr)
        return 2
    with open(args.out, "wb") as f:
        f.write(img)
    print(f"{args.out}: {len(img)} bytes, load/entry per ELF, name {name!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
