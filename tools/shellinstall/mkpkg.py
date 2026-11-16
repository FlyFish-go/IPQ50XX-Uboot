#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the installer package and the one-line command for the stock shell.

  mkpkg.py --bin out/arm/ipqi --version v0.2.1-si1 \
           --entry uboot/cmcc-mr3000d-ci.mbn=path/to/u-boot.mbn \
           --url https://... [--url ...] --out out/pkg

Writes <out>/ipqi-<version>.bin, <out>/stub.sh, <out>/command.txt.
Layout of the appended data: see src/payload.h."""
import argparse, base64, gzip, hashlib, os, struct

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bin', required=True)
    ap.add_argument('--version', required=True)
    ap.add_argument('--entry', action='append', default=[], help='name=path')
    ap.add_argument('--url', action='append', default=[])
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if len(a.version.encode()) > 47:
        raise SystemExit('version too long')

    data = bytearray(open(a.bin, 'rb').read())
    table = []
    for e in a.entry:
        name, path = e.split('=', 1)
        if len(name.encode()) > 47:
            raise SystemExit('entry name too long: ' + name)
        blob = open(path, 'rb').read()
        table.append((name, len(data), len(blob), hashlib.sha256(blob).digest()))
        data += blob
    table_off = len(data)
    for name, off, n, sha in table:
        data += name.encode().ljust(48, b'\0') + struct.pack('<II', off, n) + sha
    data += b'IPQIPKG1' + struct.pack('<II', len(table), table_off) + a.version.encode().ljust(48, b'\0')

    os.makedirs(a.out, exist_ok=True)
    pkg = os.path.join(a.out, 'ipqi-%s.bin' % a.version)
    open(pkg, 'wb').write(data)
    sha = hashlib.sha256(data).hexdigest()

    stub = open(os.path.join(HERE, 'stub', 'stub.sh.in')).read()
    html = open(os.path.join(HERE, 'stub', 'upload.html')).read().strip()
    for k, v in (('@UPLOAD_HTML@', html), ('@VERSION@', a.version), ('@SHA256@', sha),
                 ('@SIZE@', str(len(data))), ('@URLS@', ' '.join(a.url))):
        stub = stub.replace(k, v)
    if "'" in ' '.join(a.url):
        raise SystemExit('quote in url')
    open(os.path.join(a.out, 'stub.sh'), 'w').write(stub)
    b64 = base64.b64encode(gzip.compress(stub.encode(), 9, mtime=0)).decode()
    cmd = "echo '%s' | base64 -d | gunzip | sh\n" % b64
    open(os.path.join(a.out, 'command.txt'), 'w').write(cmd)
    print('package %s  %d bytes  sha256 %s' % (pkg, len(data), sha))
    print('command %d bytes' % len(cmd))


if __name__ == '__main__':
    main()
