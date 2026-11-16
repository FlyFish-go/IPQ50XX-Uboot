#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify final release checksums and record old/new whole-partition hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'release-tools'))
import appsbl_packager


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dist', type=Path, required=True)
    ap.add_argument('--old', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    pins = {line.split()[1].lstrip('*'): line.split()[0]
            for line in (a.dist / 'SHA256SUMS').read_text().splitlines()}
    rows = []
    for board in 'abcd':
        name = f'h3c-hw-{board}.mbn'
        new, old = (a.dist / name).read_bytes(), (a.old / name).read_bytes()
        appsbl_packager.verify_mbn(new)
        appsbl_packager.verify_mbn(old)
        if sha(new) != pins[name]:
            raise ValueError('release checksum mismatch: ' + name)
        banner = lambda b: re.search(rb'U-Boot 2016[^\0]+', b).group().decode()
        label = banner(new)
        if 'v0.2.0-' not in label or 'v0.2.0-rc' in label:
            raise ValueError('not the final v0.2.0 banner')
        differences = [i for i, (x, y) in enumerate(zip(old, new)) if x != y]
        rows.append(dict(board=board.upper(), file=name, bytes=len(new), sha256=sha(new),
                         partition_sha256=sha(appsbl_packager.padded_partition(new)),
                         old_sha256=sha(old), old_partition_sha256=sha(appsbl_packager.padded_partition(old)),
                         old_banner=banner(old), new_banner=label,
                         differing_bytes=len(differences), same_size=len(old) == len(new),
                         first_difference=min(differences), last_difference=max(differences),
                         raw_difference_is_only_banner=False))
    a.out.write_text(json.dumps(dict(schema='bb-final-release-audit-v1', boards=rows), indent=2) + '\n')
    print('final v0.2.0: four MBN checksums/containers/banners verified')
    for row in rows:
        print(row['board'], 'partition', row['partition_sha256'], 'raw differing bytes', row['differing_bytes'])


if __name__ == '__main__':
    main()
