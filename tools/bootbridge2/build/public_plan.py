#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Provenance-directed COPY/LITERAL plan. OEM payload is always source COPY.

Unlike the LAB matcher, this compiler never encodes OEM bytes in XOR masks.
Every literal has a named owner: our file's compressed block, generated
filesystem/container metadata, or the reviewed DT edit and checksum bytes.
"""
import hashlib
import re
import struct

PEB, LEB = 131072, 126976


def digest(data):
    return hashlib.sha256(data).hexdigest()


def volume_map(ubi):
    result = {}
    for at in range(0, len(ubi), PEB):
        if ubi[at:at + 4] != b'UBI#':
            continue
        vid, dat = struct.unpack_from('>II', ubi, at + 16)
        if ubi[at + vid:at + vid + 4] != b'UBI!':
            continue
        vol, lnum = struct.unpack_from('>II', ubi, at + vid + 8)
        if vol < 5:
            size = struct.unpack_from('>I', ubi, at + vid + 20)[0] if ubi[at + vid + 5] == 2 else LEB
            result.setdefault(vol, []).append((lnum * LEB, at + dat, size))
    return result


def translate(mapping, offset, size):
    stop = offset + size
    found = 0
    for logical, physical, length in sorted(mapping):
        lo, hi = max(offset, logical), min(stop, logical + length)
        if hi > lo:
            found += hi - lo
            yield lo - offset, physical + lo - logical, hi - lo
    if found != size:
        raise ValueError('logical range is not fully backed by the UBI input')


def fdt_items(data):
    _, _, st, strings = struct.unpack_from('>4I', data)
    strings_size, = struct.unpack_from('>I', data, 32)
    table = data[strings:strings + strings_size]
    pos, path, items = st, [], {}
    while True:
        token, = struct.unpack_from('>I', data, pos)
        pos += 4
        if token == 1:
            end = data.index(b'\0', pos) + 1
            path.append(data[pos:end - 1].decode())
            key = '/' + '/'.join(path[1:])
            items[(key, '@node')] = (pos, end - pos)
            pos = (end + 3) & ~3
        elif token == 2:
            path.pop()
        elif token == 3:
            size, name_at = struct.unpack_from('>II', data, pos)
            pos += 8
            name = table[name_at:table.index(b'\0', name_at)].decode()
            items[('/' + '/'.join(path[1:]), name)] = (pos, size)
            pos = (pos + size + 3) & ~3
        elif token == 9:
            break
        elif token != 4:
            raise ValueError('bad FDT token during provenance walk')
    for at in range(len(table)):
        if at == 0 or table[at - 1] == 0:
            stop = table.index(b'\0', at) + 1
            items[('@strings', table[at:stop].decode())] = (strings + at, stop - at)
    return items


def fdt_provenance(old, new, old_base=0, new_base=0):
    before, after = fdt_items(old), fdt_items(new)
    for key, (at, size) in sorted(after.items(), key=lambda x: x[1]):
        raw = new[at:at + size]
        if key in before:
            src, length = before[key]
            original = old[src:src + length]
            if raw == original:
                yield new_base + at, size, old_base + src
            elif key[1] == 'data' and raw[:4] == original[:4] == b'\xd0\x0d\xfe\xed':
                yield from fdt_provenance(original, raw, old_base + src, new_base + at)
        # Everything not yielded is freshly serialized FDT framing, a reviewed
        # replacement property, or a checksum. transform_kernel validates the
        # complete property diff against its pinned allowlist before this walk.


def compile_plan(source, target, stock_ubi, bridge_ubi, fit_offset, kernel, root_ranges,
                 root_manifest, root_used, root_files):
    source_ubi = source.find(stock_ubi)
    if source_ubi < 0 or source.find(stock_ubi, source_ubi + 1) >= 0:
        raise ValueError('official UBI is not unique')
    sm, tm = volume_map(stock_ubi), volume_map(bridge_ubi)
    # Non-overlapping leaf spans override the generated container default.
    marks = []

    def mark(at, size, origin, source_at=None):
        if size:
            if source_at is not None and target[at:at + size] != source[source_at:source_at + size]:
                raise ValueError('provenance COPY differs: ' + origin)
            marks.append((at, size, origin, source_at))

    def stream(vol, logical, size, origin, source_logical=None):
        for rel, dst, count in translate(tm[vol], logical, size):
            if source_logical is None:
                mark(fit_offset + dst, count, origin)
            else:
                for rel2, src, n in translate(sm[vol], source_logical + rel, count):
                    mark(fit_offset + dst + rel2, n, origin, source_ubi + src)

    # The unchanged source header and kernel runs include even 1-byte spans;
    # a minimum-match heuristic must never turn a short OEM span into data.
    for start, stop in [(0, 160)]:
        pos = start
        while pos < stop:
            equal = source[pos] == target[pos]
            end = pos + 1
            while end < stop and (source[end] == target[end]) == equal:
                end += 1
            mark(pos, end - pos, 'official:header' if equal else 'generated:header', pos if equal else None)
            pos = end
    original_kernel = b''.join(stock_ubi[p:p + n] for _, p, n in sorted(sm[0]))
    cursor = 0
    for at, size, source_at in sorted(fdt_provenance(original_kernel, kernel)):
        if at > cursor:
            stream(0, cursor, at - cursor, 'generated:reviewed-DT-and-FIT-metadata')
        stream(0, at, size, 'official:kernel-and-DT', source_at)
        cursor = at + size
    if cursor < len(kernel):
        stream(0, cursor, len(kernel) - cursor, 'generated:reviewed-DT-and-FIT-metadata')
    for vol, name in [(1, 'wifi_fw'), (2, 'bt_fw')]:
        length = sum(n for _, _, n in sm[vol])
        stream(vol, 0, length, 'official:' + name, 0)
    for r in root_ranges:
        stream(3, r['offset'], r['size'],
               ('official:' if r['source'] == 'official' else 'ours:') + r['file'],
               r['source_offset'] if r['source'] == 'official' else None)
    # Fill the gaps in the root with newly written metadata, never old tables.
    root_spans = sorted((r['offset'], r['offset'] + r['size']) for r in root_ranges)
    cursor = 0
    for start, end in root_spans + [(root_used, root_used)]:
        if start > cursor:
            stream(3, cursor, start - cursor, 'generated:squashfs-metadata')
        cursor = end

    ops, payload, literals, copies = [], bytearray(), [], []
    padding = {}
    for byte in (0, 255):
        match = max(re.finditer(bytes([byte]) + b'{32,}', source),
                    key=lambda m: m.end() - m.start(), default=None)
        if match is None:
            raise ValueError('no constant padding block in official input')
        padding[byte] = (match.start(), min(65536, match.end() - match.start()))

    def emit_copy(at, size):
        if ops and ops[-1][0] == 1 and ops[-1][1] + ops[-1][2] == at:
            ops[-1][2] += size
        else:
            ops.append([1, at, size])

    def literal(at, size, origin):
        raw = target[at:at + size]
        # Repeated standard padding needs no distributed data.
        pos = 0
        for m in re.finditer(rb'\x00{32,}|\xff{32,}', raw):
            if m.start() > pos:
                store(at + pos, raw[pos:m.start()], origin)
            remaining = m.end() - m.start()
            while remaining:
                source_at, capacity = padding[raw[m.start()]]
                n = min(capacity, remaining)
                emit_copy(source_at, n)
                remaining -= n
            pos = m.end()
        if pos < size:
            store(at + pos, raw[pos:], origin)

    def store(at, raw, origin):
        literals.append(dict(target_offset=at, data_offset=len(payload), bytes=len(raw),
                             origin=origin, sha256=digest(raw)))
        ops.append([2, 0, len(raw)])
        payload.extend(raw)

    cursor = 0
    for at, size, origin, source_at in sorted(marks):
        if at < cursor:
            raise ValueError('overlapping provenance spans')
        if at > cursor:
            literal(cursor, at - cursor, 'generated:container-and-padding')
        if source_at is None:
            literal(at, size, origin)
        else:
            copies.append(dict(target_offset=at, source_offset=source_at, bytes=size, origin=origin))
            emit_copy(source_at, size)
        cursor = at + size
    if cursor < len(target):
        literal(cursor, len(target) - cursor, 'generated:container-and-padding')
    if len(ops) > 262144:
        raise ValueError('too many public plan operations')
    rebuilt = bytearray()
    data_at = 0
    for kind, off, size in ops:
        rebuilt += source[off:off + size] if kind == 1 else payload[data_at:data_at + size]
        if kind == 2: data_at += size
    if rebuilt != target or data_at != len(payload):
        raise ValueError('public plan reconstruction mismatch')
    # No debug paths, OEM file bytes, or opaque XOR masks are acceptable here.
    if any(p in payload for p in (b'/home/', b'/Users/')):
        raise ValueError('private path in public literal data; use release/stripped ARM programs')
    for entry in root_manifest:
        if entry['source'] == 'ours':
            entry['sha256'] = digest(root_files[entry['file']])
    audit = dict(schema='bb-public-provenance-v1', input_sha256=digest(source),
                 base_sha256=digest(target), data_sha256=digest(payload),
                 no_xor=True, literal_bytes=len(payload), literals=literals,
                 official_copies=copies, root_files=root_manifest)
    plan = dict(inSize=len(source), inSha=digest(source), outSize=len(target), outSha=digest(target),
                ops=ops, data=dict(size=len(payload), sha=digest(payload)))
    return plan, bytes(payload), audit
