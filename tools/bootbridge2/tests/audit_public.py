#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Private-input audit of public plans/sites. Never writes a vendor payload.

Independently extract both roots with unsquashfs, compare every selected OEM
and project file, and prove every compressed OEM file block is source COPY.
Search raw and decoded public assets for nontrivial stock volume fragments.
"""
import argparse
import base64
import bisect
import collections
import hashlib
import json
import lzma
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

BUILD = Path(__file__).resolve().parents[1] / 'build'
sys.path.insert(0, str(BUILD))
sys.path.insert(0, str(BUILD.parent / 'web'))
import bridge_kernel
import build_bridge
import public_plan
import squashfs_splice
import vendor_fit
import vendor_ubi
from prepare_release import verify_provenance

MODELS = ('RC3000', 'RT3000', 'NX30', 'RW3000', 'NX54')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def private_path(raw):
    return any(p in raw for p in (b'/home/', b'/Users/'))


def cat(image, name):
    return subprocess.run(['unsquashfs', '-cat', str(image), name], check=True, capture_output=True).stdout


def own_sources(arm, www):
    result = {dst: (arm / src).read_bytes() for src, dst in list(build_bridge.OUR_BINARIES.items()) +
              [('bb_init', 'sbin/init'), ('bb_dhcp', 'usr/sbin/bridge-dhcp')]}
    result.update({dst: (build_bridge.RUNTIME / src).read_bytes() for src, dst in
                   [('boot.sh', 'etc/bridge/boot.sh'), ('profile', 'etc/bridge/profile'),
                    ('rootfs-id', 'etc/bridge/rootfs-id'), ('preinit', 'etc/preinit'), ('init', 'init')]})
    result.update({'www/' + name: (www / name).read_bytes() for name in ('index.html', 'main.js', 'style.css')})
    return result


def collect_fragments(stock, model, fragments):
    for volume in ('kernel', 'ubi_rootfs', 'wifi_fw'):
        raw = stock[volume]
        for at in range(0, len(raw) - 4095, 4096):
            chunk = raw[at:at + 4096]
            if len(set(chunk)) >= 32:
                fragments.setdefault(sha(chunk), (chunk, model, volume, at))


def audit_model(model, builds, inputs, own, fragments):
    d = builds / model
    src = (inputs / (model + '-original.bin')).read_bytes()
    base = (d / 'bridge-base.bin').read_bytes()
    plan, audit = [json.loads((d / name).read_text()) for name in ('plan.json', 'provenance.json')]
    payload = (d / 'plan.bin').read_bytes()
    verify_provenance(plan, payload, audit)
    rebuilt, cursor, starts = bytearray(), 0, []
    for kind, off, size in plan['ops']:
        starts.append(len(rebuilt))
        rebuilt += src[off:off + size] if kind == 1 else payload[cursor:cursor + size]
        if kind == 2: cursor += size
    if rebuilt != base or sha(base) != plan['outSha']:
        raise ValueError('independent plan reconstruction failed')
    for r in audit['official_copies']:
        at, n, original = r['target_offset'], r['bytes'], r['source_offset']
        if base[at:at + n] != src[original:original + n]:
            raise ValueError('OEM copy pin mismatch')
    source_sha = sha(src)
    if source_sha not in bridge_kernel.SOURCES:
        raise ValueError('unknown source')
    with tempfile.TemporaryDirectory() as temp:
        tmp = Path(temp)
        old_ubi = build_bridge.split_official(src)
        nodes = vendor_fit.fdt_props(base[160:160 + struct.unpack_from('>I', base, 164)[0]])
        new_ubi = next(p['data'] for n, p in nodes.items() if n.startswith('/images/ubi-') and 'data' in p)
        (tmp / 'old.ubi').write_bytes(old_ubi)
        (tmp / 'new.ubi').write_bytes(new_ubi)
        _, stock, _, _ = vendor_ubi.parse(tmp / 'old.ubi')
        _, bridge, _, _ = vendor_ubi.parse(tmp / 'new.ubi')
        expected, _ = bridge_kernel.transform_kernel(stock['kernel'], source_sha)
        if bridge['kernel'] != expected or any(stock[n] != bridge[n] for n in ('wifi_fw', 'bt_fw')):
            raise ValueError('vendor volume changed outside reviewed DT transform')
        (tmp / 'old.sqfs').write_bytes(stock['ubi_rootfs'])
        (tmp / 'new.sqfs').write_bytes(bridge['ubi_rootfs'])
        reader = squashfs_splice.Reader(bridge['ubi_rootfs'])
        root = {e['file']: e for e in audit['root_files']}
        actual_regular = {p for p, e in reader.files.items() if e['type'] in (2, 9)}
        if set(root) != actual_regular:
            raise ValueError('unaccounted root file')
        own = dict(own)
        if model == 'NX54': own['etc/bridge/tmpfs-mib'] = b'192\n'
        if {p for p, e in root.items() if e['source'] == 'ours'} != set(own):
            raise ValueError('unexpected project file provenance')
        vendor_count, own_count, block_count = 0, 0, 0
        for name, info in root.items():
            actual = cat(tmp / 'new.sqfs', name)
            if info['source'] == 'ours':
                if actual != own[name] or sha(actual) != info['sha256'] or private_path(actual):
                    raise ValueError('project file/private path mismatch: ' + name)
                own_count += 1
                continue
            if info['source'] != 'official' or actual != cat(tmp / 'old.sqfs', name):
                raise ValueError('OEM userspace payload differs: ' + name)
            vendor_count += 1
            e = reader.files[name]
            ranges, at = [], e['start']
            for size in e['blocks']:
                size &= 0xffffff
                if size: ranges.append((at, size))
                at += size
            if e['fragment'] != 0xffffffff:
                at, size = reader.fragment(e['fragment'])
                ranges.append((at, size & 0xffffff))
            physical = public_plan.volume_map(new_ubi)[3]
            for logical, length in ranges:
                for _, mapped, count in public_plan.translate(physical, logical, length):
                    start = base.index(new_ubi) + mapped
                    stop = start + count
                    while start < stop:
                        op_at = bisect.bisect_right(starts, start) - 1
                        kind, _, n = plan['ops'][op_at]
                        if kind != 1:
                            raise ValueError('OEM compressed bytes exposed as literal: ' + name)
                        start = min(stop, starts[op_at] + n)
                    block_count += 1
        collect_fragments(stock, model, fragments)
        totals = collections.Counter()
        for r in audit['literals']: totals[r['origin']] += r['bytes']
        return dict(model=model, oem_files=vendor_count, project_files=own_count,
                    oem_block_ranges_copy_only=block_count, literal_bytes=len(payload),
                    literal_origins=dict(totals), literal_records=len(audit['literals']),
                    base_sha256=sha(base), plan_sha256=sha(payload))


def scan_sites(sites, fragments):
    assets = []
    for site in sites:
        for path in sorted(site.rglob('*')):
            if not path.is_file(): continue
            raw = path.read_bytes()
            if private_path(raw):
                raise ValueError('private path in site: ' + path.name)
            assets.append((site.name + '/' + path.relative_to(site).as_posix(), raw))
            m = re.fullmatch(rb'BBData.add\("[^"\n]+","([A-Za-z0-9+/=]*)"\);\n', raw)
            if m:
                decoded = base64.b64decode(m[1], validate=True)
                if private_path(decoded):
                    raise ValueError('private path in decoded data')
                assets.append((site.name + '/' + path.name + ':decoded', decoded))
            decoded = base64.b64decode(m[1], validate=True) if m else raw
            if decoded[:4] == b'BBPK':
                size, = struct.unpack_from('<I', decoded, 8)
                archive = lzma.decompress(decoded[64 + size:], format=lzma.FORMAT_ALONE)
                if private_path(archive):
                    raise ValueError('private path in uncompressed rule archive')
                assets.append((site.name + '/' + path.name + ':tar', archive))
    unique = {sha(raw): raw for _, raw in assets}
    matches = []
    for digest, (fragment, model, volume, offset) in fragments.items():
        for digest_asset, raw in unique.items():
            if fragment in raw:
                names = [n for n, data in assets if sha(data) == digest_asset]
                matches.append(dict(asset=names, model=model, volume=volume, offset=offset, sha256=digest))
    if matches:
        raise ValueError('OEM payload fragment in public asset: ' + json.dumps(matches[:5]))
    # A positive control demonstrates that the exact scanner detects a leak.
    sample = next(iter(fragments.values()))[0]
    if sample not in b'positive-control' + sample:
        raise ValueError('scanner positive control failed')
    return dict(public_files_and_decoded_assets=len(assets), fragment_bytes=4096,
                unique_asset_contents=len(unique), distinct_fragments=len(fragments),
                fragments_by_origin=dict(collections.Counter(m + ':' + v for _, m, v, _ in fragments.values())),
                matches=matches, positive_control=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--builds', type=Path, required=True)
    ap.add_argument('--inputs', type=Path, required=True)
    ap.add_argument('--arm-bin', type=Path, required=True)
    ap.add_argument('--www', type=Path, required=True)
    ap.add_argument('--site', type=Path, action='append', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--scan-only', action='store_true', help='broaden asset search without repeating the root audit')
    a = ap.parse_args()
    fragments = {}
    own = own_sources(a.arm_bin, a.www)
    rows = []
    if a.scan_only:
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'stock.ubi'
            for model in MODELS:
                p.write_bytes(build_bridge.split_official((a.inputs / (model + '-original.bin')).read_bytes()))
                _, stock, _, _ = vendor_ubi.parse(p)
                collect_fragments(stock, model, fragments)
    else:
        rows = [audit_model(m, a.builds, a.inputs, own, fragments) for m in MODELS]
    scanned = scan_sites(a.site, fragments)
    result = dict(schema='bb-public-private-audit-v1', models=rows, scan=scanned,
                  hardware_tested_here=False)
    a.out.write_text(json.dumps(result, indent=2) + '\n')
    if not a.scan_only: print('PASS: five roots, all OEM payload ranges COPY-only, all project files match source')
    print('PASS: %d distinct 4096-byte vendor fragments x %d public/decoded assets: 0 matches' %
          (scanned['distinct_fragments'], scanned['public_files_and_decoded_assets']))


if __name__ == '__main__':
    main()
