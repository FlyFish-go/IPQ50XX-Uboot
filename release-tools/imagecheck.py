#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Sanity-check an APPSBL build before it is flashed or released.

    imagecheck.py --build-dir OUT/<board> --version 460c68cfb --env-size 0x10000 \\
                  [--mbn appsbl.mbn] [--partition-size 0x140000]
    imagecheck.py --elf u-boot --mbn appsbl.mbn --text-base 0x4a920000 ...

Four checks, each PASS / FAIL / SKIP:
  size     the MBN fits in the APPSBL partition (default 0x140000);
  entry    the ELF entry point equals CONFIG_SYS_TEXT_BASE;
  banner   the image carries the "U-Boot ..." banner and it contains the
           expected git version;
  env      CONFIG_ENV_SIZE equals the size from the board's data sheet.
--build-dir is a U-Boot output directory: it supplies the ELF (u-boot), the
text base and the env size (include/autoconf.mk).  Without --mbn the MBN is
built in memory with appsbl_packager, which is exactly what a release writes;
with --mbn the file is also compared with that rebuild.
Exit status 1 on any FAIL.
"""
import argparse
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import appsbl_packager  # noqa: E402


def num(s):
    s = s.strip()
    m = re.fullmatch(r"\(?\s*(\d+)\s*<<\s*(\d+)\s*\)?", s)
    if m:
        return int(m.group(1)) << int(m.group(2))
    m = re.fullmatch(r"(\d+)[kK]", s)
    if m:
        return int(m.group(1)) << 10
    return int(s, 0)


def conf_num(conf, name):
    """Value of CONFIG_<name> from autoconf.mk, following $(CONFIG_...) references."""
    v = conf[name]
    for _ in range(8):
        m = re.fullmatch(r"\$\((CONFIG_\w+)\)", v.strip())
        if not m:
            break
        v = conf[m.group(1)]
    return num(v)


def autoconf(path):
    d = {}
    try:
        with open(path) as fh:
            for line in fh:
                m = re.match(r'(CONFIG_\w+)=(.*)', line.rstrip())
                if m:
                    d[m.group(1)] = m.group(2).strip('"')
    except OSError:
        pass
    return d


def elf_entry(data):
    if data[:4] != b"\x7fELF" or len(data) < 28:
        raise ValueError("not an ELF file")
    return struct.unpack_from("<I", data, 24)[0]


def banners(data):
    return [m.group(0).decode("ascii", "replace")
            for m in re.finditer(rb"U-Boot [0-9][ -~]{10,200}", data)]


def check(elf, mbn, partition_size, text_base, version, env_size, conf_env):
    res = []

    def add(name, ok, msg):
        res.append((name, "SKIP" if ok is None else ("PASS" if ok else "FAIL"), msg))

    rebuilt = None
    try:
        rebuilt = appsbl_packager.package_elf(elf)
    except appsbl_packager.PackError as e:
        add("mbn", False, "packager rejects the ELF: %s" % e)
    if mbn is None:
        mbn = rebuilt
    elif rebuilt is not None:
        add("mbn", mbn == rebuilt, "file %s the packager's output for this ELF"
            % ("equals" if mbn == rebuilt else "differs from"))
    if mbn is not None:
        add("size", len(mbn) <= partition_size,
            "mbn %d bytes (%#x), partition %#x, slack %d" %
            (len(mbn), len(mbn), partition_size, partition_size - len(mbn)))
    else:
        add("size", False, "no MBN")

    try:
        entry = elf_entry(elf)
        add("entry", None if text_base is None else entry == text_base,
            "entry %#x, text base %s" % (entry, "unknown" if text_base is None else "%#x" % text_base))
    except ValueError as e:
        add("entry", False, str(e))

    bs = banners(elf)
    if not bs:
        add("banner", False, "no U-Boot banner string in the image")
    elif version is None:
        add("banner", None, "no --version given; banner: %s" % bs[0])
    else:
        hit = [b for b in bs if version in b]
        add("banner", bool(hit), ("version %s found in: %s" % (version, hit[0])) if hit
            else "version %s not in banner: %s" % (version, bs[0]))

    if conf_env is None:
        add("env", None, "no autoconf.mk, CONFIG_ENV_SIZE unknown")
    elif env_size is None:
        add("env", None, "no --env-size given; CONFIG_ENV_SIZE = %#x" % conf_env)
    else:
        add("env", conf_env == env_size,
            "CONFIG_ENV_SIZE %#x, expected %#x" % (conf_env, env_size))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build-dir")
    ap.add_argument("--elf")
    ap.add_argument("--mbn")
    ap.add_argument("--partition-size", default="0x140000")
    ap.add_argument("--text-base")
    ap.add_argument("--version", help="git version the banner must contain")
    ap.add_argument("--env-size", help="expected env size, e.g. 0x10000 or 64K")
    a = ap.parse_args(argv)

    elf_path = a.elf or (os.path.join(a.build_dir, "u-boot") if a.build_dir else None)
    if not elf_path:
        ap.error("need --build-dir or --elf")
    conf = autoconf(os.path.join(a.build_dir, "include", "autoconf.mk")) if a.build_dir else {}
    text_base = num(a.text_base) if a.text_base else (
        conf_num(conf, "CONFIG_SYS_TEXT_BASE") if "CONFIG_SYS_TEXT_BASE" in conf else None)
    conf_env = conf_num(conf, "CONFIG_ENV_SIZE") if "CONFIG_ENV_SIZE" in conf else None
    with open(elf_path, "rb") as fh:
        elf = fh.read()
    mbn = None
    if a.mbn:
        with open(a.mbn, "rb") as fh:
            mbn = fh.read()

    res = check(elf, mbn, num(a.partition_size), text_base, a.version,
                num(a.env_size) if a.env_size else None, conf_env)
    for name, st, msg in res:
        print("%-4s %-6s %s" % (st, name, msg))
    return 1 if any(st == "FAIL" for _n, st, _m in res) else 0


if __name__ == "__main__":
    sys.exit(main())
