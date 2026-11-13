#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Extract board facts from device trees, as JSON.

    dtbfacts.py INPUT [-o facts.json] [--machid 0x8040000] [--defconfig FILE]

INPUT is a plain .dtb, a dtb_combined.bin, or any firmware image (an APPSBL
partition, an MBN, a U-Boot binary).  The tool scans the file for FDT blobs
(magic d0 0d fe ed, validated and fully parsed) and also inside gzip streams,
because Qualcomm U-Boot keeps its board table compressed.  Every blob found
yields one facts record, so a stock U-Boot image gives one record per machid.

Pure Python, no dependencies.  Facts only; nothing is judged here (see
dtbcheck.py).
"""
import argparse
import json
import re
import struct
import sys
import zlib

FDT_MAGIC = b"\xd0\x0d\xfe\xed"
BEGIN_NODE, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9


class FdtError(ValueError):
    pass


def parse_fdt(blob):
    """Return the root node as {"props": {name: bytes}, "kids": {name: node}}."""
    if len(blob) < 40 or blob[:4] != FDT_MAGIC:
        raise FdtError("bad magic")
    (_m, total, off_struct, off_strings, _rsv, version, last_comp,
     _boot, size_strings, size_struct) = struct.unpack(">10I", blob[:40])
    if total > len(blob) or total < 40:
        raise FdtError("bad totalsize")
    if version < 16 or last_comp > 17:
        raise FdtError("unsupported version")
    if off_struct + size_struct > total or off_strings + size_strings > total:
        raise FdtError("bad offsets")
    st = blob[off_struct:off_struct + size_struct]
    strs = blob[off_strings:off_strings + size_strings]
    pos = 0
    stack = []
    root = None
    while True:
        if pos + 4 > len(st):
            raise FdtError("truncated structure")
        tag = struct.unpack(">I", st[pos:pos + 4])[0]
        pos += 4
        if tag == BEGIN_NODE:
            end = st.index(b"\0", pos)
            name = st[pos:end].decode("ascii", "replace")
            pos = (end + 1 + 3) & ~3
            node = {"props": {}, "kids": {}}
            if stack:
                stack[-1]["kids"][name] = node
            elif root is None:
                root = node
            else:
                raise FdtError("second root")
            stack.append(node)
        elif tag == END_NODE:
            if not stack:
                raise FdtError("unbalanced")
            stack.pop()
        elif tag == PROP:
            ln, nameoff = struct.unpack(">II", st[pos:pos + 8])
            pos += 8
            if not stack or nameoff >= len(strs) or pos + ln > len(st):
                raise FdtError("bad property")
            name = strs[nameoff:strs.index(b"\0", nameoff)].decode("ascii", "replace")
            stack[-1]["props"][name] = st[pos:pos + ln]
            pos = (pos + ln + 3) & ~3
        elif tag == NOP:
            pass
        elif tag == END:
            break
        else:
            raise FdtError("bad tag %#x" % tag)
    if stack or root is None:
        raise FdtError("unbalanced")
    return root


def find_blobs(data):
    """Yield (origin, offset, blob) for every valid FDT in data or in a gzip stream."""
    def scan(buf, origin):
        i = 0
        while True:
            i = buf.find(FDT_MAGIC, i)
            if i < 0:
                return
            if i + 8 <= len(buf):
                total = struct.unpack(">I", buf[i + 4:i + 8])[0]
                if 40 <= total <= len(buf) - i:
                    try:
                        parse_fdt(buf[i:i + total])
                        yield origin, i, buf[i:i + total]
                    except (FdtError, ValueError, struct.error):
                        pass
            i += 4

    yield from scan(data, "raw")
    i = 0
    while True:
        i = data.find(b"\x1f\x8b\x08", i)
        if i < 0:
            break
        try:
            out = zlib.decompressobj(31).decompress(data[i:])
        except zlib.error:
            out = b""
        if FDT_MAGIC in out:
            yield from scan(out, "gzip@%#x" % i)
        i += 3


# --- property decoding ------------------------------------------------------

def cells(node, name):
    p = node["props"].get(name)
    if p is None or len(p) % 4:
        return None
    return list(struct.unpack(">%dI" % (len(p) // 4), p))


def cell(node, name):
    c = cells(node, name)
    return c[0] if c else None


def strings(node, name):
    p = node["props"].get(name)
    if p is None:
        return None
    return [s.decode("utf-8", "replace") for s in p.split(b"\0") if s]


def hexs(v):
    return None if v is None else "0x%x" % v


def walk(node, path=""):
    yield path, node
    for name, kid in node["kids"].items():
        yield from walk(kid, path + "/" + name)


def kid(node, name):
    return node["kids"].get(name)


# --- facts ------------------------------------------------------------------

def gpio_entry(n):
    e = {"gpio": cell(n, "gpio"), "func": cell(n, "func")}
    return {k: v for k, v in e.items() if v is not None}


def gmac_facts(cfg):
    out = {}
    if cfg is None:
        return out
    out["count"] = cell(cfg, "gmac_count")
    out["ext_mdio_gpio"] = cells(cfg, "ext_mdio_gpio")
    out["gephy_led"] = cell(cfg, "gephy_led")
    for unit in ("gmac1", "gmac2"):
        g = kid(cfg, unit + "_cfg")
        if g is None:
            continue
        f = {"phy_address": cell(g, "phy_address"),
             "phy_external_link": cell(g, "phy_external_link")}
        if cell(g, "s17c_switch_enable") == 1:
            f["phy_type"] = "qca8337-switch"
            f["reset_gpio"] = cell(g, "switch_gpio")
            f["switch_ports"] = cell(g, "switch_port_count")
            f["switch_phy_addrs"] = cells(g, "switch_phy_address")
            f["phy_address"] = None  # the PHY address is meaningless behind a switch
        elif cell(g, "8033_gpio") is not None:
            f["phy_type"] = "qca8033"
            f["reset_gpio"] = cell(g, "8033_gpio")
        elif cell(g, "napa_gpio") is not None:
            f["phy_type"] = "napa-phy"
            f["reset_gpio"] = cell(g, "napa_gpio")
        elif cell(g, "phy_address") == 7:
            f["phy_type"] = "internal-gephy"
        else:
            f["phy_type"] = "other"
        out[unit] = {k: v for k, v in f.items() if v is not None}
    return {k: v for k, v in out.items() if v is not None}


def group_facts(root, names, default_active=None):
    """leds / keys: {node-name: {gpio, active_level, label}} from the first group present."""
    res = {}
    for gname in names:
        grp = kid(root, gname)
        if grp is None:
            continue
        for name, n in grp["kids"].items():
            g = cell(n, "gpio")
            if g is None:
                continue
            e = {"gpio": g}
            al = cell(n, "active_level")
            if al is not None:
                e["active_level"] = "low" if al == 1 else "high"
            lab = strings(n, "label")
            if lab:
                e["label"] = lab
            res[name] = e
    return res


def uart_facts(root):
    pins = {}
    cons = None
    for path, n in walk(root):
        sg = kid(n, "serial_gpio")
        if sg is None:
            continue
        for name, p in sg["kids"].items():
            pins[name] = gpio_entry(p)
        cons = path
    return {"node": cons, "pins": pins}


def mac_source(defconfig_text):
    if defconfig_text is None:
        return None
    part = re.search(r'^CONFIG_MAC_PART_NAME="(.*)"', defconfig_text, re.M)
    off = re.search(r"^CONFIG_MAC_OFFSET_IN_PART=(\S+)", defconfig_text, re.M)
    cnt = re.search(r"^CONFIG_MAC_COUNT=(\d+)", defconfig_text, re.M)
    if not part:
        return None
    r = {"partition": part.group(1), "offset": off.group(1) if off else None}
    if cnt:
        r["count"] = int(cnt.group(1))
    return r


def facts_of(root, defconfig_text=None):
    machid = cell(root, "machid")
    f = {
        "machid": hexs(machid),
        "config_name": strings(root, "config_name"),
        "model": (strings(root, "model") or [None])[0],
        "uart": uart_facts(root),
        "gmac": gmac_facts(kid(root, "gmac_cfg")),
        # stock U-Boot DTBs call the key group "button"
        "keys": {n: e["gpio"] for n, e in group_facts(root, ["keys", "button"]).items()},
        "leds": group_facts(root, ["leds"]),
    }
    ms = mac_source(defconfig_text)
    if ms:
        f["mac_source"] = ms
    return f


def extract(path, machid=None, defconfig=None):
    with open(path, "rb") as fh:
        data = fh.read()
    dc = None
    if defconfig:
        with open(defconfig) as fh:
            dc = fh.read()
    blobs = []
    seen = set()
    for origin, off, blob in find_blobs(data):
        if blob in seen:
            continue
        seen.add(blob)
        f = facts_of(parse_fdt(blob), dc)
        if f["machid"] is None:
            continue
        if machid and int(machid, 0) != int(f["machid"], 0):
            continue
        f["origin"] = "%s+%#x" % (origin, off)
        blobs.append(f)
    return blobs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--machid", help="keep only the blob with this machid")
    ap.add_argument("--defconfig", help="add the MAC source from this defconfig")
    a = ap.parse_args(argv)
    blobs = extract(a.input, a.machid, a.defconfig)
    if not blobs:
        print("no device tree with a machid found in %s" % a.input, file=sys.stderr)
        return 1
    txt = json.dumps({"blobs": blobs}, indent=1, sort_keys=True) + "\n"
    if a.output:
        open(a.output, "w").write(txt)
    else:
        sys.stdout.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
