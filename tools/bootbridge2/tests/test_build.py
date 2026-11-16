#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Offline NX54 image checks. Inputs: NX54_OFFICIAL, BB_PACK, BB_BUILDS.

BB_BUILDS holds the five build directories, including NX54. Temporary files
respect TMPDIR. All negative cases operate on ordinary copies, never devices.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

BUILD = Path(__file__).resolve().parents[1] / "build"
sys.path.insert(0, str(BUILD))
import bridge_kernel
import build_bridge
import inject_pack
import vendor_fit
import vendor_ubi


@unittest.skipUnless(os.environ.get("NX54_OFFICIAL") and os.environ.get("BB_BUILDS"),
                     "NX54_OFFICIAL and BB_BUILDS required")
class NX54Image(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official = Path(os.environ["NX54_OFFICIAL"]).read_bytes()
        cls.identity = hashlib.sha256(cls.official).hexdigest()
        cls.directory = Path(os.environ["BB_BUILDS"]) / "NX54"
        cls.base = (cls.directory / "bridge-base.bin").read_bytes()
        cls.final = (cls.directory / "bridge.bin").read_bytes()
        cls.layout = json.loads((cls.directory / "layout.json").read_text())
        cls.pack = Path(os.environ["BB_PACK"]).read_bytes()
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "stock.ubi"
            p.write_bytes(build_bridge.split_official(cls.official))
            cls.meta, cls.stock, _, _ = vendor_ubi.parse(p)
            nodes = vendor_fit.fdt_props(cls.final[160:160 + struct.unpack_from(">I", cls.final, 164)[0]])
            images = [p for n, p in nodes.items() if n.startswith("/images/") and n.count("/") == 2]
            cls.outer_images = [n for n in nodes if n.startswith("/images/") and n.count("/") == 2]
            p.write_bytes(images[0]["data"])
            cls.output_meta, cls.output, _, _ = vendor_ubi.parse(p)

    def test_exact_reviewed_source(self):
        self.assertEqual(bridge_kernel.SOURCES[self.identity][0], "NX54V100R014")
        self.assertEqual(len(self.official), 32702464)
        length = struct.unpack_from(">I", self.official, 164)[0]
        self.assertEqual(len(self.official) - 160 - length, 18948)
        self.assertFalse(any(self.official[160 + length:]))

    def test_header_fit_and_tail(self):
        self.assertEqual(self.final[:6], b"H3C_+k")
        self.assertIn(b"NX54V100R999\0", self.final[:160])
        self.assertEqual(len(self.outer_images), 1)
        self.assertTrue(self.outer_images[0].startswith("/images/ubi-"))
        fit_len = struct.unpack_from(">I", self.final, 164)[0]
        self.assertEqual(self.final[160 + fit_len:], bytes(16384))
        self.assertEqual(sum(x[0] for x in struct.iter_unpack(">I", self.final[64:])) & 0xffffffff,
                         0xffffffff)

    def test_kernel_and_nonroute_images_preserved(self):
        a = vendor_fit.fdt_props(self.stock["kernel"])
        b = vendor_fit.fdt_props(self.output["kernel"])
        self.assertEqual(a["/images/kernel@1"], b["/images/kernel@1"])
        for n in a:
            if not n.startswith("/images/fdt@mp03.1/") and n != "/images/fdt@mp03.1":
                self.assertEqual(a[n], b[n], n)
        self.assertEqual(len([n for n in b if n.startswith("/configurations/config@")]), 20)

    def test_route_changes_are_bounded(self):
        a = vendor_fit.fdt_props(vendor_fit.fdt_props(self.stock["kernel"])["/images/fdt@mp03.1"]["data"])
        b = vendor_fit.fdt_props(vendor_fit.fdt_props(self.output["kernel"])["/images/fdt@mp03.1"]["data"])
        disabled = bridge_kernel.source_profile(self.identity)["disabled"]
        self.assertEqual(bridge_kernel._changes(a, b), {(n, "status") for n in disabled} |
                         {("/chosen", "bootargs"), ("/", "h3c,bridge-profile")})
        self.assertEqual(a["/soc/ess-instance/ess-switch1@1"], b["/soc/ess-instance/ess-switch1@1"])
        self.assertEqual(a["/soc/gpio_keys/button@1"], b["/soc/gpio_keys/button@1"])

    def test_volume_table_and_firmware_preserved(self):
        self.assertEqual(self.meta["volume_table"], self.output_meta["volume_table"])
        for n in ("wifi_fw", "bt_fw"):
            self.assertEqual(self.stock[n], self.output[n])
        self.assertLessEqual(sum(v["reserved_pebs"] for v in self.meta["volume_table"]) + 4, 362)
        self.assertEqual(self.output_meta["volume_table"][3]["type"], "dynamic")

    def test_reject_wrong_source_or_repeated_transform(self):
        with self.assertRaises(ValueError):
            bridge_kernel.transform_kernel(self.output["kernel"], self.identity)
        with self.assertRaises(ValueError):
            bridge_kernel.transform_kernel(self.stock["kernel"], "0" * 64)
        with self.assertRaises(ValueError):
            bridge_kernel.transform_kernel(self.stock["kernel"][:-1], self.identity)

    def test_injection_preserves_transport_tail(self):
        self.assertEqual(inject_pack.inject(self.base, self.layout, self.pack), self.final)
        # Even a layout with a matching base hash cannot legitimize nonzero tail bytes.
        bad = self.base[:-1] + b"\1"
        layout = copy.deepcopy(self.layout)
        layout["base"]["sha256"] = hashlib.sha256(bad).hexdigest()
        with self.assertRaisesRegex(ValueError, "transport tail"):
            inject_pack.inject(bad, layout, self.pack)

    def test_checker_rejects_missing_tail_and_nonzero_tail(self):
        with tempfile.TemporaryDirectory() as t:
            for data in (self.final[:-16384], self.final[:-4] + b"\0\0\0\1"):
                b = bytearray(data)
                # Keep outer sizes and checksum consistent so only the tail rule fails.
                struct.pack_into(">I", b, 68, len(b) - 64)
                struct.pack_into(">I", b, 80, len(b) - 160)
                struct.pack_into(">I", b, 72, 0)
                total = sum(x[0] for x in struct.iter_unpack(">I", b[64:])) & 0xffffffff
                struct.pack_into(">I", b, 72, (0xffffffff - total) & 0xffffffff)
                p = Path(t) / "bad.bin"
                p.write_bytes(b)
                r = subprocess.run([sys.executable, str(BUILD / "check_image.py"), "--image", str(p),
                                    "--official", os.environ["NX54_OFFICIAL"]], capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("FIT length", r.stdout + r.stderr)

    def test_web_multipart_truncation_margin(self):
        fit_len = struct.unpack_from(">I", self.final, 164)[0]
        for adjustment in (-516, 310):
            uploaded = self.final[160:]
            uploaded = uploaded[:len(uploaded) + adjustment] if adjustment < 0 else uploaded + bytes(adjustment)
            # OEM dumpimage sees an intact FIT despite the buggy multipart length.
            self.assertEqual(vendor_fit.fdt_props(uploaded[:fit_len]),
                             vendor_fit.fdt_props(self.final[160:160 + fit_len]))

    def test_tmpfs_space_setting(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "bridge.sqfs"
            p.write_bytes(self.output["ubi_rootfs"])
            r = subprocess.run(["unsquashfs", "-cat", str(p), "etc/bridge/tmpfs-mib"], capture_output=True)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"192\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
