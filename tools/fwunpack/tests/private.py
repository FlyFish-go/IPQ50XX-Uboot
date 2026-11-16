#!/usr/bin/env python3
"""Private regression. Use python3 -I. Inputs come only from environment.
Writes firmware, manifests and full results exclusively to $OUT.
"""
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(os.environ['OUT'])
RESULTS = OUT / 'results'
RESULTS.mkdir(parents=True, exist_ok=True)
TMP = OUT / 'tmp'
TMP.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR']=str(TMP)
inputs = []
entries = json.loads(Path(os.environ['H3C_OEM_CATALOG']).read_text())['entries']
for e in entries:
    inputs.append({'group': 'h3c', 'path': e['package_paths'][0]})
inputs.append({'group': 'nx54', 'path': os.environ['NX54_OFFICIAL']})
for key, group, pattern in [('JIKE_DIR','jike','*.bin'), ('XIAOMI_DIR','xiaomi','*'),
                             ('RUIJIE_DIR','ruijie','inputs/*.bin'),
                             ('RUIJIE_DIR','ruijie','inputs/zfgeng/*.bin'),
                             ('RAX3000QY_DIR','rax3000qy','backup/p1/rootfs*.bin')]:
    for p in sorted(Path(os.environ[key]).glob(pattern)):
        if p.is_file(): inputs.append({'group':group,'path':str(p)})
for p in sorted((OUT/'samples').glob('**/*')):
    if p.is_file() and p.suffix.lower() in ('.bin','.img','.itb','.ubi'):
        inputs.append({'group':'download','path':str(p)})
manifest = {'inputs':inputs,'output':str(OUT/'extracted'),'results':str(RESULTS/'private.json')}
manifest_path = OUT/'private-manifest.json'
manifest_path.write_text(json.dumps(manifest))
subprocess.run(['node', str(ROOT/'tools/fwunpack/tests/private-batch.cjs'),str(manifest_path)],check=True)
rows=json.loads((RESULTS/'private.json').read_text())
spec=importlib.util.spec_from_file_location('production',ROOT/'tools/fwunpack/tests/production.py')
production=importlib.util.module_from_spec(spec)
spec.loader.exec_module(production)
host=production.host
lib=production.make_lib(TMP)
for row,x in zip(rows,inputs):
    row['input_sha256']=hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()
    if not row['ok']:
        assert (row['group']=='jike' and any(t in row['name'] for t in ('_AX3000X_', '_B3000_', '_WP963_'))) or (row['group']=='download' and 'linksys_mx2000' in row['name']), row
        continue
    ubi=bytearray(Path(row['output']).read_bytes())
    ret,pebs,reserved=host.validate(lib,ubi)
    row['production_validator']=ret
    assert ret==0,(row['name'],ret)
    if row['group']=='h3c':
        e=next(e for e in entries if e['package_paths'][0]==x['path'])
        assert row['input_sha256']==e['package_sha256']
        assert row['sha256']==e['fit_ubi_sha256']
        assert ubi==host.extract_ubi(e)
        # Independent reconstruction from physical VID headers, sorted by lnum.
        vol=next(v for v in row['volumes'] if v['name']==e['rootfs_volume_name'])['id']
        blocks={}
        for o in range(0,len(ubi),131072):
            if struct.unpack_from('>I',ubi,o+2048+8)[0]==vol:
                n=struct.unpack_from('>I',ubi,o+2048+12)[0]
                blocks[n]=ubi[o+4096:o+131072]
        data=b''.join(blocks[n] for n in sorted(blocks))
        size=struct.unpack_from('<Q',data,40)[0]
        assert size==e['rootfs_bytes_used']
        assert hashlib.sha256(data[:size]).hexdigest()==e['rootfs_sha256']
        row['catalog_ubi_and_rootfs']='PASS'
    row.pop('output',None)  # Shareable results contain names, never private paths.
(RESULTS/'private.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
lines=['| 组 | 文件 | 结果 | UBI SHA-256 / 原因 | C 校验 |','|---|---|---|---|---|']
for r in rows: lines.append(f"| {r['group']} | {r['name']} | {'通过' if r['ok'] else '无输出'} | {r.get('sha256',r.get('error'))} | {r.get('production_validator','—')} |")
(RESULTS/'private.md').write_text('\n'.join(lines)+'\n')
print('PRIVATE:',len(rows),'inputs,',sum(r['ok'] for r in rows),'UBI,',sum(not r['ok'] for r in rows),'no output')

subprocess.run(['node',str(ROOT/'tools/fwunpack/tests/private-new-version.cjs'),str(manifest_path)],check=True)
