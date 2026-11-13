#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compare our board facts against a reference, field by field.

    dtbcheck.py OURS REFERENCE [--machid 0x8040000] [--expect expect.json] [--md]

OURS and REFERENCE are each either a facts JSON written by dtbfacts.py or
anything dtbfacts.py can read (a .dtb, dtb_combined.bin, an APPSBL image).
The reference blob is chosen by machid; our own machid decides when OURS
holds a single blob.

Each field ends up as one of
    SAME       both sides agree
    DIFF       both sides have the value and they differ
    REF_ONLY   the reference has it, ours does not (a pin we forgot?)
    OURS_ONLY  ours has it, the reference does not (usually fine: stock
               U-Boot trees carry no LED or key nodes for many boards)
An --expect file ([{"path": "gmac.gmac1.phy_type", "reason": "..."}, ...])
marks known differences as EXPECTED; "path" may end in "*" as a prefix match.
Exit status is 1 when a DIFF or REF_ONLY is left unexplained.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtbfacts  # noqa: E402

IGNORED = {"model", "origin"}


def load(path, machid=None):
    with open(path, "rb") as fh:
        head = fh.read(1)
    if head == b"{":
        with open(path) as fh:
            blobs = json.load(fh)["blobs"]
        if machid:
            blobs = [b for b in blobs if int(b["machid"], 0) == int(machid, 0)]
        return blobs
    return dtbfacts.extract(path, machid)


def flatten(facts):
    flat = {}

    def put(path, v):
        if v is not None:
            flat[path] = v

    put("machid", facts.get("machid"))
    cn = facts.get("config_name")
    put("config_name", cn[0] if cn else None)
    for name, p in facts.get("uart", {}).get("pins", {}).items():
        for k, v in p.items():
            put("uart.%s.%s" % (name, k), v)
    for k, v in facts.get("gmac", {}).items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                put("gmac.%s.%s" % (k, kk), vv)
        else:
            put("gmac." + k, v)
    for name, gpio in facts.get("keys", {}).items():
        put("keys.%s" % name, gpio)
    for e in facts.get("leds", {}).values():
        put("leds.gpio%d" % e["gpio"], "present")
        put("leds.gpio%d.active_level" % e["gpio"], e.get("active_level"))
    for k, v in facts.get("mac_source", {}).items():
        put("mac_source." + k, v)
    return flat


def compare(ours, ref, expect=()):
    a, b = flatten(ours), flatten(ref)
    rows = []
    for path in sorted(set(a) | set(b)):
        if path in IGNORED:
            continue
        va, vb = a.get(path), b.get(path)
        if path in a and path in b:
            st = "SAME" if va == vb else "DIFF"
        elif path in b:
            st = "REF_ONLY"
        else:
            st = "OURS_ONLY"
        reason = None
        if st in ("DIFF", "REF_ONLY"):
            for e in expect:
                p = e["path"]
                if p == path or (p.endswith("*") and path.startswith(p[:-1])):
                    reason = e.get("reason", "expected")
                    break
        rows.append((st, path, va, vb, reason))
    return rows


def pick(blobs, machid, what):
    if not blobs:
        sys.exit("%s: no device tree with machid %s" % (what, machid or "(any)"))
    if len(blobs) > 1:
        ids = sorted({b["machid"] for b in blobs})
        print("note: %s has %d blobs (machids %s), using the first (%s); "
              "pass --machid to choose" % (what, len(blobs), ", ".join(ids),
                                           blobs[0].get("origin")), file=sys.stderr)
    return blobs[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ours")
    ap.add_argument("reference")
    ap.add_argument("--machid")
    ap.add_argument("--expect", help="JSON file with explained differences")
    ap.add_argument("--md", action="store_true", help="print a Markdown table")
    ap.add_argument("--all", action="store_true", help="also list SAME rows")
    a = ap.parse_args(argv)

    ours_blobs = load(a.ours, a.machid)
    ours = pick(ours_blobs, a.machid, "ours")
    ref = pick(load(a.reference, a.machid or ours["machid"]), a.machid or ours["machid"], "reference")
    expect = []
    if a.expect:
        with open(a.expect) as fh:
            expect = json.load(fh)
    rows = compare(ours, ref, expect)

    counts = {}
    bad = 0
    for st, path, va, vb, reason in rows:
        key = "EXPECTED" if reason else st
        counts[key] = counts.get(key, 0) + 1
        if st in ("DIFF", "REF_ONLY") and not reason:
            bad += 1
        if st == "SAME" and not a.all:
            continue
        v = lambda x: "-" if x is None else json.dumps(x)  # noqa: E731
        if a.md:
            print("| %s | %s | %s | %s | %s |" % (key, path, v(va), v(vb), reason or ""))
        else:
            print("%-9s %-34s ours=%s ref=%s%s" % (key, path, v(va), v(vb),
                                                   "  # " + reason if reason else ""))
    print("# machid %s: %s" % (ours["machid"],
                               ", ".join("%s=%d" % kv for kv in sorted(counts.items()))))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
