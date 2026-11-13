#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
import os, struct, sys, unittest, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkramuimg as m


def fake_elf(load=m.RAM_TEXT_BASE, entry=None, body=b"\x01\x02\x03\x04" * 8, extra_bss=64):
    entry = load if entry is None else entry
    ehdr = b"\x7fELF\x01\x01\x01" + bytes(9) + struct.pack("<HHIIIIIHHHHHH", 2, 40, 1, entry, 52, 0, 0, 52, 32, 2, 0, 0, 0)
    off = 52 + 64
    phs = struct.pack("<8I", 1, off, load, load, len(body), len(body) + extra_bss, 7, 0x10000)
    phs += struct.pack("<8I", 1, off + len(body), load + len(body), load + len(body), 0, 16, 6, 0x10000)
    return ehdr + phs + body


class Test(unittest.TestCase):
    def test_header(self):
        img = m.make_uimage(fake_elf(), "x-ram", timestamp=7)
        magic, hcrc, ts, size, load, ep, dcrc, os_, arch, typ, comp = struct.unpack_from(">7I4B", img)
        self.assertEqual((magic, ts, size, load, ep), (m.IH_MAGIC, 7, 32, m.RAM_TEXT_BASE, m.RAM_TEXT_BASE))
        self.assertEqual((os_, arch, typ, comp), (5, 2, 2, 0))
        self.assertEqual(dcrc, zlib.crc32(img[64:]) & 0xFFFFFFFF)
        zeroed = img[:4] + bytes(4) + img[8:64]
        self.assertEqual(hcrc, zlib.crc32(zeroed) & 0xFFFFFFFF)
        self.assertEqual(img[32:64].rstrip(b"\0"), b"x-ram")

    def test_wrong_link_address(self):
        with self.assertRaises(m.ImageError):
            m.make_uimage(fake_elf(load=0x4A920000), "x")

    def test_entry_outside(self):
        with self.assertRaises(m.ImageError):
            m.make_uimage(fake_elf(entry=0x50000000), "x")

    def test_not_elf(self):
        with self.assertRaises(m.ImageError):
            m.make_uimage(b"hello" * 20, "x")


if __name__ == "__main__":
    unittest.main()
