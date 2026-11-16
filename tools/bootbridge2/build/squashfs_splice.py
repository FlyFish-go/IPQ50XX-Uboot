#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the small bridge root without recompressing any OEM file data.

OEM data/fragment blocks are copied verbatim from the user's SquashFS. Our
files come from a temporary -no-fragments mksquashfs image. New inode,
directory, fragment and ID tables contain only generated filesystem metadata.
The returned ranges identify every byte of file payload and its provenance.

Disk format reference (SquashFS v4):
https://github.com/plougher/squashfs-tools/blob/master/squashfs-tools/squashfs_fs.h
This is a deliberately bounded host builder, not a general filesystem reader.
"""
import lzma
import os
from pathlib import Path
import stat
import struct
import zlib

INVALID = 0xffffffff
ABSENT = 0xffffffffffffffff
BLOCK = 131072


class Reader:
    def __init__(self, data):
        self.data = data
        fields = struct.unpack_from('<5I6H8Q', data)
        magic, _, _, self.block, self.fragments, self.comp = fields[:6]
        self.root, self.used, _, _, self.it, self.dt, self.ft, _ = fields[11:]
        if magic != 0x73717368 or fields[9:11] != (4, 0) or self.block not in (BLOCK, 262144) or self.comp not in (1, 4):
            raise ValueError('unsupported SquashFS source geometry/compression')
        if not 96 <= self.it < self.used <= len(data):
            raise ValueError('bad SquashFS source bounds')
        self.files = {}
        self.walk('', self.root)

    def decompress(self, raw):
        return zlib.decompress(raw) if self.comp == 1 else lzma.decompress(raw)

    def metadata(self, at):
        size, = struct.unpack_from('<H', self.data, at)
        raw = self.data[at + 2:at + 2 + (size & 0x7fff)]
        decoded = raw if size & 0x8000 else self.decompress(raw)
        if not 0 < len(decoded) <= 8192:
            raise ValueError('bad SquashFS metadata block')
        return decoded, at + 2 + len(raw)

    def read_meta(self, start, offset, count):
        result = bytearray()
        while count:
            raw, following = self.metadata(start)
            take = min(count, len(raw) - offset)
            if take <= 0:
                raise ValueError('SquashFS metadata offset')
            result += raw[offset:offset + take]
            count -= take
            start, offset = following, 0
        return bytes(result)

    def inode(self, ref):
        at, off = self.it + (ref >> 16), ref & 0xffff
        base = self.read_meta(at, off, 16)
        typ, mode, _, _, _, number = struct.unpack('<4H2I', base)
        fixed = {1: 32, 2: 32, 3: 24, 4: 24, 5: 24, 6: 20, 7: 20,
                 8: 40, 9: 56, 10: 24, 11: 28, 12: 28, 13: 24, 14: 24}
        if typ not in fixed:
            raise ValueError('unsupported SquashFS inode type %s' % typ)
        raw = self.read_meta(at, off, fixed[typ])
        item = dict(type=typ, mode=mode, number=number)
        if typ == 1:
            start, _, size, offset, _ = struct.unpack_from('<IIHHI', raw, 16)
            item.update(start=start, size=size - 3, offset=offset)
        elif typ == 8:
            _, size, start, _, _, offset, _ = struct.unpack_from('<4I2HI', raw, 16)
            item.update(start=start, size=size - 3, offset=offset)
        elif typ in (2, 9):
            if typ == 2:
                start, fragment, offset, size = struct.unpack_from('<4I', raw, 16)
            else:
                start, size, _, _, fragment, offset, _ = struct.unpack_from('<3Q4I', raw, 16)
            count = size // self.block + (fragment == INVALID and size % self.block != 0)
            raw = self.read_meta(at, off, fixed[typ] + count * 4)
            blocks = list(struct.unpack_from('<%dI' % count, raw, fixed[typ])) if count else []
            item.update(start=start, size=size, fragment=fragment, offset=offset, blocks=blocks)
        elif typ in (3, 10):
            _, size = struct.unpack_from('<II', raw, 16)
            item['link'] = self.read_meta(at, off, 24 + size)[24:].decode()
        return item

    def walk(self, name, ref):
        item = self.inode(ref)
        self.files[name] = item
        if item['type'] not in (1, 8):
            return
        raw = self.read_meta(self.dt + item['start'], item['offset'], item['size']) if item['size'] else b''
        pos = 0
        while pos < len(raw):
            count, start, _ = struct.unpack_from('<3I', raw, pos)
            pos += 12
            if count >= 256:
                raise ValueError('bad SquashFS directory header')
            for _ in range(count + 1):
                offset, _, _, length = struct.unpack_from('<HhHH', raw, pos)
                pos += 8
                child = raw[pos:pos + length + 1].decode()
                pos += length + 1
                if child in ('.', '..') or '/' in child:
                    raise ValueError('bad SquashFS entry name')
                self.walk(name + '/' + child if name else child, start << 16 | offset)

    def fragment(self, index):
        if not 0 <= index < self.fragments:
            raise ValueError('fragment index outside table')
        table, = struct.unpack_from('<Q', self.data, self.ft + (index // 512) * 8)
        raw = self.read_meta(table, (index % 512) * 16, 16)
        start, size, _ = struct.unpack('<QII', raw)
        return start, size


def splice(stock, own, root, oem_files, epoch):
    """Return (SquashFS bytes, complete file-payload provenance, file manifest)."""
    sources = {'official': Reader(stock), 'ours': Reader(own)}
    if (sources['official'].comp, sources['official'].block) != (sources['ours'].comp, sources['ours'].block):
        raise ValueError('OEM and generated SquashFS compression/block size differ')
    root = Path(root)
    paths = [''] + sorted(p.relative_to(root).as_posix() for p in root.rglob('*'))
    # /dev/console is supplied by the pseudo file, never created on the host.
    paths = sorted(set(paths) | {'dev/console'})
    numbers = {p: i + 1 for i, p in enumerate(paths)}
    data = bytearray(96)
    ranges, manifest, fragments, fragment_ids = [], [], [], {}
    entries = {}

    def payload(source, start, size, path, kind):
        raw = sources[source].data[start:start + size]
        if len(raw) != size:
            raise ValueError('file block outside SquashFS')
        at = len(data)
        data.extend(raw)
        ranges.append(dict(offset=at, size=size, source=source, source_offset=start,
                           file=path, kind=kind))
        return at

    for path in paths:
        p = root / path
        mode = p.lstat().st_mode if path != 'dev/console' else stat.S_IFCHR | 0o600
        if stat.S_ISDIR(mode):
            entries[path] = dict(type=1, mode=stat.S_IMODE(mode))
        elif stat.S_ISLNK(mode):
            entries[path] = dict(type=3, mode=stat.S_IMODE(mode), link=os.readlink(p))
        elif stat.S_ISCHR(mode):
            entries[path] = dict(type=5, mode=0o600)
        elif stat.S_ISREG(mode):
            source = 'official' if path in oem_files else 'ours'
            old = sources[source].files[path]
            if old['type'] not in (2, 9) or old['size'] != p.stat().st_size:
                raise ValueError('file source/size mismatch: ' + path)
            start, cursor = len(data), old['start']
            for size in old['blocks']:
                length = size & 0xffffff
                if length:
                    payload(source, cursor, length, path, 'data')
                    cursor += length
            frag = INVALID
            if old['fragment'] != INVALID:
                key = (source, old['fragment'])
                if key not in fragment_ids:
                    at, size = sources[source].fragment(old['fragment'])
                    new_at = payload(source, at, size & 0xffffff, path, 'fragment')
                    fragment_ids[key] = len(fragments)
                    fragments.append((new_at, size))
                frag = fragment_ids[key]
            entries[path] = dict(type=2, mode=stat.S_IMODE(mode), start=start, size=old['size'],
                                 fragment=frag, offset=old['offset'], blocks=old['blocks'])
            manifest.append(dict(file=path, source=source, bytes=old['size']))
        else:
            raise ValueError('unsupported staged file: ' + path)

    # One uncompressed metadata block per inode/directory avoids compressed
    # offset fixups and leaves no OEM metadata encoded in a literal payload.
    inode_sizes = {p: (32 + 4 * len(e['blocks']) if e['type'] == 2 else
                      24 + len(e['link'].encode()) if e['type'] == 3 else
                      24 if e['type'] == 5 else 32) for p, e in entries.items()}
    refs, pos = {}, 0
    for p in paths:
        if inode_sizes[p] > 8192:
            raise ValueError('inode exceeds bounded metadata size')
        refs[p] = pos << 16
        pos += inode_sizes[p] + 2
    directories, dir_refs = bytearray(), {}
    for p in paths:
        if entries[p]['type'] != 1:
            continue
        children = [c for c in paths if c and Path(c).parent.as_posix() == (p or '.')]
        raw = bytearray()
        for c in children:
            name = Path(c).name.encode()
            # One entry per header; no dependence on inode number deltas.
            raw += struct.pack('<3I', 0, refs[c] >> 16, numbers[c])
            raw += struct.pack('<HhHH', 0, 0, entries[c]['type'], len(name) - 1) + name
        if len(raw) > 8192:
            raise ValueError('directory exceeds bounded metadata size')
        dir_refs[p] = (len(directories), len(raw))
        if raw:
            directories += struct.pack('<H', 0x8000 | len(raw)) + raw
    it = len(data)
    for p in paths:
        e = entries[p]
        raw = struct.pack('<4H2I', e['type'], e['mode'], 0, 0, epoch, numbers[p])
        if e['type'] == 1:
            at, size = dir_refs[p]
            parent = str(Path(p).parent) if p else ''
            if parent == '.': parent = ''
            links = 2 + sum(Path(c).parent.as_posix() == (p or '.') and entries[c]['type'] == 1
                            for c in paths if c)
            raw += struct.pack('<IIHHI', at, links, size + 3, 0, numbers[parent])
        elif e['type'] == 2:
            raw += struct.pack('<4I', e['start'], e['fragment'], e['offset'], e['size'])
            raw += struct.pack('<%dI' % len(e['blocks']), *e['blocks']) if e['blocks'] else b''
        elif e['type'] == 3:
            link = e['link'].encode()
            raw += struct.pack('<II', 1, len(link)) + link
        elif e['type'] == 5:
            raw += struct.pack('<II', 1, (5 << 8) | 1)
        data += struct.pack('<H', 0x8000 | len(raw)) + raw
    dt = len(data)
    data += directories
    fragment_indexes = []
    for i in range(0, len(fragments), 512):
        raw = b''.join(struct.pack('<QII', at, size, 0) for at, size in fragments[i:i + 512])
        fragment_indexes.append(len(data))
        data += struct.pack('<H', 0x8000 | len(raw)) + raw
    ft = len(data) if fragments else ABSENT
    for at in fragment_indexes:
        data += struct.pack('<Q', at)
    id_data = len(data)
    data += struct.pack('<HI', 0x8004, 0)
    ids = len(data)
    data += struct.pack('<Q', id_data)
    flags = (1 << 0) | (1 << 9) | (1 << 11)  # plain inodes/IDs, no xattrs/export table
    block = sources['official'].block
    struct.pack_into('<5I6H8Q', data, 0, 0x73717368, len(paths), epoch, block, len(fragments),
                     sources['official'].comp, block.bit_length() - 1, flags, 1, 4, 0, refs[''], len(data), ids,
                     ABSENT, it, dt, ft, ABSENT)
    return bytes(data), ranges, manifest
