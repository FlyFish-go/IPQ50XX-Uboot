#!/usr/bin/env python3
"""Synthetic differential check against the actual rescue C validator.
Run with python3 -I; no proprietary files or extra Python dependencies.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('production',ROOT/'tools/fwunpack/tests/production.py')
production=importlib.util.module_from_spec(spec)
spec.loader.exec_module(production)
host=production.host
# JS mutations include CRC repair to reach checks beyond header checksums.
script=r'''
const fs=require('node:fs'),f=require('./tools/fwunpack/tests/fixtures.cjs'),fw=require('./tools/fwunpack/core.js');
fs.writeFileSync(process.argv[1],f.ubi);const rows=[{edits:[],repair:[],ok:true}];
for(const base of [0,2048,4096,131072,131072+2048,2*131072+2048,3*131072+2048,3*131072+4096])
 for(let i=0;i<64;i++){
  const edits=[[base+i,f.ubi[base+i]^0x81]],b=Buffer.from(f.ubi);for(const [o,v]of edits)b[o]=v;
  const repairs=[[],[base],[0,2048,4096]];
  for(const repair of repairs){const c=Buffer.from(b);for(const o of repair){const len=o%131072===4096?168:60;c.writeUInt32BE(fw.crc32(c.subarray(o,o+len),true),o+len);}
   let ok=true;try{fw.validateUBI(c);}catch(_){ok=false;}rows.push({edits,repair,ok});
  }
 }
console.log(JSON.stringify(rows));
'''
with tempfile.TemporaryDirectory(prefix='fwunpack-validator-',dir=os.environ.get('TMPDIR')) as td:
    td=Path(td)
    lib=production.make_lib(td)
    raw=subprocess.check_output(['node','-e',script,str(td/'synthetic.ubi')],cwd=ROOT)
    rows=json.loads(raw)
    original=(td/'synthetic.ubi').read_bytes()
    accepted=0
    for row in rows:
        b=bytearray(original)
        for off,value in row['edits']: b[off]=value
        for off in row['repair']:
            length=168 if off%131072==4096 else 60
            import zlib
            crc=zlib.crc32(b[off:off+length]) ^ 0xffffffff
            b[off+length:off+length+4]=crc.to_bytes(4,'big')
        ret,_,_=host.validate(lib,b)
        if row['ok']:
            accepted+=1
            assert ret==0,('JS accepted but rescue refused',row,ret)
    print(f'VALIDATOR_PARITY_PASS: {len(rows)} cases, {accepted} JS-accepted images also accepted by production C')
