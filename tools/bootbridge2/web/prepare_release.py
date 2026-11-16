#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Seal reviewed public-only inputs; never copy a bridge/OEM image into release.

Run privately after --public-plan builds and the independent payload audit.
The output may be committed. GitHub Pages needs only these inputs and Python.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

MODELS = ('RC3000', 'RT3000', 'NX30', 'RW3000', 'NX54')
FILES = ('plan.json', 'plan.bin', 'layout.json', 'provenance.json')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_provenance(plan, data, audit):
    if audit.get('schema') != 'bb-public-provenance-v1' or audit.get('no_xor') is not True:
        raise ValueError('public provenance required')
    if (sha(data), len(data), plan['inSha'], plan['outSha']) != (
            plan['data']['sha'], plan['data']['size'], audit['input_sha256'], audit['base_sha256']):
        raise ValueError('plan/provenance pins differ')
    if sha(data) != audit['data_sha256'] or len(data) != audit['literal_bytes']:
        raise ValueError('literal data pin differs')
    at = 0
    for item in audit['literals']:
        if item['data_offset'] != at or not item['origin'].startswith(('ours:', 'generated:')):
            raise ValueError('unowned/overlapping literal')
        end = at + item['bytes']
        if item['bytes'] <= 0 or end > len(data) or sha(data[at:end]) != item['sha256']:
            raise ValueError('literal record pin differs')
        at = end
    if at != len(data) or any(op[0] not in (1, 2) for op in plan['ops']):
        raise ValueError('opaque/XOR/unaccounted public data')
    at = target = literal = 0
    for kind, off, size in plan['ops']:
        if size <= 0:
            raise ValueError('invalid operation size')
        if kind == 1:
            if not 0 <= off <= plan['inSize'] - size:
                raise ValueError('COPY outside source')
        else:
            row = audit['literals'][literal]
            if off or row['data_offset'] != at or row['target_offset'] != target or row['bytes'] != size:
                raise ValueError('literal operation/provenance mismatch')
            at += size
            literal += 1
        target += size
    if at != len(data) or target != plan['outSize'] or literal != len(audit['literals']):
        raise ValueError('incomplete plan')


def verify_release(directory):
    directory = Path(directory)
    pins = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or name in pins:
            raise ValueError('unsafe checksum member')
        path = directory / rel
        if path.is_symlink() or sha(path.read_bytes()) != digest:
            raise ValueError('release checksum mismatch: ' + name)
        pins[name] = digest
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if actual != set(pins) | {'SHA256SUMS'}:
        raise ValueError('unlisted public release member')
    meta = json.loads((directory / 'release.json').read_text())
    expected = {'release.json', 'rules.txt', 'rules.bbpack', 'rules-nx54.txt', 'rules-nx54.bbpack'}
    expected |= {f'builds/{m}/{f}' for m in MODELS for f in FILES}
    if set(pins) != expected or meta['schema'] != 'bb-web-release-v1':
        raise ValueError('release allowlist/schema differs')
    for model in MODELS:
        d = directory / 'builds' / model
        verify_provenance(json.loads((d / 'plan.json').read_text()), (d / 'plan.bin').read_bytes(),
                          json.loads((d / 'provenance.json').read_text()))
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--builds', type=Path, required=True)
    ap.add_argument('--rules', type=Path, required=True, help='folder with both rules[ -nx54 ].txt/.bbpack')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    for model in MODELS:
        d = a.out / 'builds' / model
        d.mkdir(parents=True)
        for name in FILES:
            shutil.copyfile(a.builds / model / name, d / name)
    for name in ('rules.txt', 'rules.bbpack', 'rules-nx54.txt', 'rules-nx54.bbpack'):
        shutil.copyfile(a.rules / name, a.out / name)
    meta = dict(schema='bb-web-release-v1', rule_set='BB2-R5', nx30_uboot='v0.2.0',
                nx54='testing', models=list(MODELS), format='COPY/LITERAL; no OEM payload literals')
    (a.out / 'release.json').write_text(json.dumps(meta, indent=2) + '\n')
    rows = [f'{sha(p.read_bytes())}  {p.relative_to(a.out).as_posix()}'
            for p in sorted(a.out.rglob('*')) if p.is_file()]
    (a.out / 'SHA256SUMS').write_text('\n'.join(rows) + '\n')
    verify_release(a.out)
    print(f'public release sealed: {len(rows)} files')


if __name__ == '__main__':
    main()
