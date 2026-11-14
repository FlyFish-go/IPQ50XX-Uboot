#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Self-tests for dtbfacts.py, dtbcheck.py and imagecheck.py (synthetic inputs only).

    python3 release-tools/test_dtbtools.py
"""
import gzip
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtbcheck  # noqa: E402
import dtbfacts  # noqa: E402
import imagecheck  # noqa: E402


def fdt(tree):
    """Serialise {"props": {name: bytes|int|[int]|str}, "kids": {name: tree}} to a DTB."""
    strs = bytearray()
    offs = {}
    out = bytearray()

    def pad():
        while len(out) % 4:
            out.append(0)

    def enc(v):
        if isinstance(v, bytes):
            return v
        if isinstance(v, str):
            return v.encode() + b"\0"
        if isinstance(v, int):
            v = [v]
        return struct.pack(">%dI" % len(v), *v)

    def node(name, t):
        out.extend(struct.pack(">I", 1) + name.encode() + b"\0")
        pad()
        for k, v in t.get("props", {}).items():
            if k not in offs:
                offs[k] = len(strs)
                strs.extend(k.encode() + b"\0")
            data = enc(v)
            out.extend(struct.pack(">III", 3, len(data), offs[k]) + data)
            pad()
        for k, kt in t.get("kids", {}).items():
            node(k, kt)
        out.extend(struct.pack(">I", 2))

    node("", tree)
    out.extend(struct.pack(">I", 9))
    off_struct = 40 + 16
    off_strings = off_struct + len(out)
    total = off_strings + len(strs)
    head = struct.pack(">10I", 0xd00dfeed, total, off_struct, off_strings, 40, 17, 16, 0,
                       len(strs), len(out))
    return head + bytes(16) + bytes(out) + bytes(strs)


def board(machid=0x8040000, switch_gpio=26, led=19, reset=25, uart=(20, 21)):
    return {"props": {"machid": machid, "config_name": "config@mp02.1", "model": "T"},
            "kids": {
        "serial@78AF000": {"kids": {"serial_gpio": {"kids": {
            "blsp0_uart_rx": {"props": {"gpio": uart[0], "func": 1}},
            "blsp0_uart_tx": {"props": {"gpio": uart[1], "func": 1}}}}}},
        "gmac_cfg": {"props": {"ext_mdio_gpio": [36, 37]}, "kids": {
            "gmac1_cfg": {"props": {"phy_address": 7}},
            "gmac2_cfg": {"props": {"s17c_switch_enable": 1, "switch_port_count": 4,
                                    "switch_phy_address": [0, 1, 2, 3],
                                    "switch_gpio": switch_gpio}}}},
        "keys": {"kids": {"reset": {"props": {"gpio": reset, "active_level": 1}}}},
        "leds": {"kids": {"led_a": {"props": {"gpio": led, "active_level": 0,
                                              "label": "power_led"}}}},
    }}


class Facts(unittest.TestCase):
    def test_parse_and_extract(self):
        f = dtbfacts.facts_of(dtbfacts.parse_fdt(fdt(board())))
        self.assertEqual(f["machid"], "0x8040000")
        self.assertEqual(f["uart"]["pins"]["blsp0_uart_rx"], {"gpio": 20, "func": 1})
        self.assertEqual(f["gmac"]["gmac1"]["phy_type"], "internal-gephy")
        self.assertEqual(f["gmac"]["gmac2"]["phy_type"], "qca8337-switch")
        self.assertEqual(f["gmac"]["gmac2"]["reset_gpio"], 26)
        self.assertEqual(f["keys"], {"reset": 25})
        self.assertEqual(f["leds"]["led_a"]["active_level"], "high")

    def test_image_scan_finds_gzip_and_ignores_bare_magic(self):
        a, b = fdt(board(0x8040000)), fdt(board(0x8040002, switch_gpio=39))
        table = gzip.compress(b"\0\0\0\0" + a + b"\0" * 8 + b)
        # a literal 0xd00dfeed in code must not count as a blob
        image = b"\xff" * 64 + b"\xd0\x0d\xfe\xed\0\0\1\0" + b"\xff" * 64 + table
        with tempfile.NamedTemporaryFile(suffix=".bin") as t:
            t.write(image)
            t.flush()
            blobs = dtbfacts.extract(t.name)
            self.assertEqual(sorted(x["machid"] for x in blobs), ["0x8040000", "0x8040002"])
            one = dtbfacts.extract(t.name, machid="0x8040002")
            self.assertEqual(one[0]["gmac"]["gmac2"]["reset_gpio"], 39)

    def test_truncated_blob_is_rejected(self):
        with self.assertRaises(dtbfacts.FdtError):
            dtbfacts.parse_fdt(fdt(board())[:60])


class Check(unittest.TestCase):
    def rows(self, ours, ref, expect=()):
        return {r[1]: r for r in dtbcheck.compare(
            dtbfacts.facts_of(dtbfacts.parse_fdt(fdt(ours))),
            dtbfacts.facts_of(dtbfacts.parse_fdt(fdt(ref))), expect)}

    def test_identical(self):
        rows = self.rows(board(), board())
        self.assertTrue(all(r[0] == "SAME" for r in rows.values()))

    def test_diff_and_expected(self):
        rows = self.rows(board(switch_gpio=39), board())
        self.assertEqual(rows["gmac.gmac2.reset_gpio"][0], "DIFF")
        rows = self.rows(board(switch_gpio=39), board(),
                         [{"path": "gmac.gmac2.*", "reason": "swapped on purpose"}])
        self.assertEqual(rows["gmac.gmac2.reset_gpio"][4], "swapped on purpose")

    def test_key_polarity(self):
        f = dtbfacts.facts_of(dtbfacts.parse_fdt(fdt(board())))
        self.assertEqual(f["keys_active"], {"reset": "low"})
        flipped = board()
        flipped["kids"]["keys"]["kids"]["reset"]["props"]["active_level"] = 0
        rows = self.rows(flipped, board())
        self.assertEqual(rows["keys.reset"][0], "SAME")
        self.assertEqual(rows["keys.reset.active_level"][0], "DIFF")

    def test_ref_only_and_ours_only(self):
        ref = board()
        ref["kids"]["leds"]["kids"]["led_b"] = {"props": {"gpio": 30}}
        rows = self.rows(board(), ref)
        self.assertEqual(rows["leds.gpio30"][0], "REF_ONLY")
        rows = self.rows(ref, board())
        self.assertEqual(rows["leds.gpio30"][0], "OURS_ONLY")

    def test_cli_exit_status(self):
        with tempfile.TemporaryDirectory() as d:
            for name, b in (("a", board()), ("b", board(uart=(28, 29)))):
                with open(os.path.join(d, name), "wb") as fh:
                    fh.write(fdt(b))
            devnull = open(os.devnull, "w")
            old, sys.stdout = sys.stdout, devnull
            try:
                self.assertEqual(dtbcheck.main([d + "/a", d + "/a"]), 0)
                self.assertEqual(dtbcheck.main([d + "/a", d + "/b"]), 1)
            finally:
                sys.stdout = old
                devnull.close()


def elf(entry=0x4a920000, payload=b"U-Boot 2016.01-abc123def456 (Nov 13 2026)\0" + bytes(100)):
    ph = struct.pack("<IIIIIIII", 1, 0x1000, entry, entry, len(payload), len(payload), 7, 0x1000)
    ph += struct.pack("<IIIIIIII", 0x6474E551, 0, 0, 0, 0, 0, 7, 0x10)
    head = struct.pack("<16sHHIIIIIHHHHHH", b"\x7fELF\x01\x01\x01" + bytes(9), 2, 40, 1, entry,
                       52, 0, 0, 52, 32, 2, 0, 0, 0)
    return head + ph + bytes(0x1000 - len(head) - len(ph)) + payload


class Image(unittest.TestCase):
    def run_check(self, e, **kw):
        args = dict(mbn=None, partition_size=0x140000, text_base=0x4a920000,
                    version="abc123d", env_size=0x10000, conf_env=0x10000)
        args.update(kw)
        return {n: s for n, s, _m in imagecheck.check(e, args["mbn"], args["partition_size"],
                                                       args["text_base"], args["version"],
                                                       args["env_size"], args["conf_env"])}

    def test_pass(self):
        r = self.run_check(elf())
        self.assertEqual(set(r.values()), {"PASS"})

    def test_failures(self):
        self.assertEqual(self.run_check(elf(), partition_size=0x1000)["size"], "FAIL")
        self.assertEqual(self.run_check(elf(), text_base=0x49a20000)["entry"], "FAIL")
        self.assertEqual(self.run_check(elf(), version="zzzzzzz")["banner"], "FAIL")
        self.assertEqual(self.run_check(elf(), conf_env=0x40000)["env"], "FAIL")
        self.assertEqual(self.run_check(elf(), env_size=None)["env"], "SKIP")

    def test_mbn_mismatch(self):
        good = imagecheck.appsbl_packager.package_elf(elf())
        self.assertEqual(self.run_check(elf(), mbn=good)["mbn"], "PASS")
        self.assertEqual(self.run_check(elf(), mbn=good[:-1] + b"\x01")["mbn"], "FAIL")

    def test_num(self):
        self.assertEqual(imagecheck.num("64K"), 0x10000)
        self.assertEqual(imagecheck.num("(256 << 10)"), 0x40000)
        self.assertEqual(imagecheck.conf_num({"CONFIG_A": "$(CONFIG_B)", "CONFIG_B": "(64 << 10)"},
                                             "CONFIG_A"), 0x10000)


if __name__ == "__main__":
    unittest.main()
