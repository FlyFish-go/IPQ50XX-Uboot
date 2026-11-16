#!/usr/bin/env python3
"""Independent UBI Reader geometry/volume checks and real sysupgrade parity."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

OUT=Path(os.environ['OUT'])
rows=json.loads((OUT/'results/private.json').read_text())
tool=shutil.which('ubireader_display_info')
assert tool,'UBI Reader is not installed'
chosen=[next(r for r in rows if r['group']==group and r['ok']) for group in ('h3c','nx54','jike','xiaomi','ruijie','download')]
real=next(r for r in rows if r['ok'] and 'b3000-squashfs-sysupgrade' in r['name'])
chosen.append(real)
results=[]
for index,row in enumerate(chosen):
    p=OUT/'extracted'/row['group']/(row['name']+'.ubi')
    cmd=[sys.executable,'-I','-B','-c','import sys,site,runpy; sys.path.append(site.getusersitepackages()); tool=sys.argv.pop(1);runpy.run_path(tool,run_name="__main__")',tool,str(p)]
    res=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=True,timeout=45)
    (OUT/'results'/f'ubireader-{index}-{row["group"]}.txt').write_text(res.stdout)
    for key,value in [('Min I/O',row['pageSize']),('LEB Size',row['lebSize']),('PEB Size',row['pebSize']),('Total Block Count',row['imagePEBs'])]:
        found=re.search(r'\b'+re.escape(key)+r':\s+(\d+)',res.stdout)
        assert found and int(found.group(1))==value,(row['name'],key)
    names=re.findall(r'Volume Name:([^\n]+)',res.stdout)
    assert sorted(names)==sorted(v['name']for v in row['volumes'])
    results.append({'name':row['name'],'geometry':'PASS','volume_names':'PASS'})
# Use the real NAND sysupgrade tar's exact kernel and SquashFS, never execute it.
source=OUT/'samples/openwrt'/real['name']
tmp=OUT/'ubinize-real'
tmp.mkdir(exist_ok=True)
with tarfile.open(source,'r:') as archive:
    for name in ('kernel','root'):
        members=[m for m in archive.getmembers() if re.fullmatch(r'sysupgrade-[^/]+/'+name,m.name)]
        assert len(members)==1 and members[0].isfile()
        (tmp/name).write_bytes(archive.extractfile(members[0]).read())
config=f'[kernel]\nmode=ubi\nimage={tmp}/kernel\nvol_id=0\nvol_type=dynamic\nvol_name=kernel\n[rootfs]\nmode=ubi\nimage={tmp}/root\nvol_id=1\nvol_type=dynamic\nvol_name=rootfs\n[data]\nmode=ubi\nvol_id=2\nvol_size=126976\nvol_type=dynamic\nvol_name=rootfs_data\nvol_flags=autoresize\n'
(tmp/'ubi.cfg').write_text(config)
subprocess.run([os.environ['UBINIZE'],'-p','131072','-m','2048','-s','2048','-O','2048','-e','0','-Q','0','-o',str(tmp/'host.ubi'),str(tmp/'ubi.cfg')],check=True,stdout=subprocess.DEVNULL)
host=(tmp/'host.ubi').read_bytes()
js=(OUT/'extracted'/real['group']/(real['name']+'.ubi')).read_bytes()
assert host==js,'real sysupgrade ubinize output mismatch'
results.append({'name':real['name'],'ubinize_byte_parity':'PASS','bytes':len(js),'sha256':hashlib.sha256(js).hexdigest()})
(OUT/'results/crosscheck.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print('CROSSCHECK_PASS:',len(chosen),'UBI Reader geometry/volume checks; real sysupgrade ubinize byte parity')
