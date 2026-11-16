#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Public-asset tampering/provenance tests; needs BB_PUBLIC_RELEASE."""
import copy
import json
import hashlib
import io
import lzma
import os
from pathlib import Path
import shutil
import sys
import struct
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_release import verify_provenance, verify_release


@unittest.skipUnless(os.environ.get('BB_PUBLIC_RELEASE'), 'BB_PUBLIC_RELEASE required')
class Release(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release = Path(os.environ['BB_PUBLIC_RELEASE'])
        d = cls.release / 'builds' / 'NX54'
        cls.plan = json.loads((d / 'plan.json').read_text())
        cls.data = (d / 'plan.bin').read_bytes()
        cls.audit = json.loads((d / 'provenance.json').read_text())

    def test_sealed_release(self):
        self.assertEqual(verify_release(self.release)['rule_set'], 'BB2-R6')

    def test_no_xor(self):
        self.assertEqual({o[0] for o in self.plan['ops']}, {1, 2})

    def test_each_literal_accounted(self):
        verify_provenance(self.plan, self.data, self.audit)
        self.assertEqual(sum(x['bytes'] for x in self.audit['literals']), len(self.data))

    def test_corrupt_data(self):
        with self.assertRaises(ValueError):
            verify_provenance(self.plan, self.data[:-1] + bytes([self.data[-1] ^ 1]), self.audit)

    def test_missing_owner(self):
        audit = copy.deepcopy(self.audit)
        audit['literals'][0]['origin'] = 'official:kernel'
        with self.assertRaises(ValueError): verify_provenance(self.plan, self.data, audit)

    def test_unaccounted_data(self):
        audit = copy.deepcopy(self.audit)
        audit['literals'].pop()
        with self.assertRaises(ValueError): verify_provenance(self.plan, self.data, audit)

    def test_reject_xor(self):
        plan = copy.deepcopy(self.plan)
        plan['ops'][0][0] = 3
        with self.assertRaises(ValueError): verify_provenance(plan, self.data, self.audit)

    def test_target_mapping(self):
        audit = copy.deepcopy(self.audit)
        audit['literals'][0]['target_offset'] += 1
        with self.assertRaises(ValueError): verify_provenance(self.plan, self.data, audit)

    def test_reject_extra_vendor_image(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / 'release'
            shutil.copytree(self.release, d)
            (d / 'bridge-base.bin').write_bytes(b'forbidden')
            with self.assertRaisesRegex(ValueError, 'unlisted'): verify_release(d)

    def test_checksum_required(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / 'release'
            shutil.copytree(self.release, d)
            (d / 'builds/NX54/plan.bin').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'checksum'): verify_release(d)

    def test_hidden_pack_has_no_nx54(self):
        raw = (self.release / 'rules.bbpack').read_bytes()
        rules_len, = struct.unpack_from('<I', raw, 8)
        rules = raw[64:64 + rules_len]
        self.assertNotIn(b'board NX54', rules)
        self.assertIn(b'set BB2-R6\n', rules)
        archive = lzma.decompress(raw[64 + rules_len:], format=lzma.FORMAT_ALONE)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            self.assertEqual(set(tar.getnames()), {f'candidates/h3c-hw-{g}.mbn' for g in 'abcd'})

    def test_both_packs_contain_final_release(self):
        expected = dict(a='0e7fdfc682a978e79726da6addb77fb0f157fb4ab79f6e5f1e04b1d0ca8ca926',
                        b='d14601b654ba22dd013e87a3cce2de52f91e5b86d81b48bce574e6976ae40100',
                        c='47a91ed64040b21ef73e80799894ca22b877f5312a5a12bf337f670bfe32faeb',
                        d='2f0b037a35d4504dc2260d7e29be5ac43af7c1fa7b4160a1ed43b36c82393d30')
        for name in ('rules.bbpack', 'rules-nx54.bbpack'):
            raw = (self.release / name).read_bytes()
            rules_len, = struct.unpack_from('<I', raw, 8)
            archive = lzma.decompress(raw[64 + rules_len:], format=lzma.FORMAT_ALONE)
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                for group, digest in expected.items():
                    mbn = tar.extractfile(f'candidates/h3c-hw-{group}.mbn').read()
                    self.assertEqual(hashlib.sha256(mbn).hexdigest(), digest)
                    self.assertIn(b'v0.2.0-', mbn)
                    self.assertNotIn(b'v0.2.0-rc11-', mbn)


if __name__ == '__main__': unittest.main(verbosity=2)
