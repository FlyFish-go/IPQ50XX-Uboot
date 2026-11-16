/* SPDX-License-Identifier: GPL-2.0-or-later. Mutates a private input in memory. */
const fs=require('node:fs'),assert=require('node:assert/strict'),fw=require('../core.js');
(async()=>{
 const manifest=JSON.parse(fs.readFileSync(process.argv[2])),input=manifest.inputs.find(x=>x.group==='h3c');
 const b=fs.readFileSync(input.path),original=await fw.unpack(b);
 // Change header version without relying on any value from an old release.
 b.fill(0,96,144);b.write('SYNTHETIC-FUTURE-V999R999',96);
 const t=fw.fdt(b.subarray(160)),images=t.root.children.find(n=>n.name==='images');
 const n=images.children.find(n=>n.props.data&&Buffer.from(n.props.data.subarray(0,4)).equals(Buffer.from('UBI#')));
 assert(n);const d=n.props.data,info=fw.validateUBI(d),root=info.root.blocks.get(0);
 root[1000]^=0x5a;
 // Dynamic UBI data has no VID data CRC; recompute every FIT integrity field.
 for(const h of n.children.filter(n=>/^hash(?:[-@].*)?$/.test(n.name))) {
  const algo=new TextDecoder().decode(h.props.algo).replace(/\0.*$/s,'');h.props.value.set(Buffer.from(await fw.digest(d,algo),'hex'));
 }
 const r=await fw.unpack(b);assert.equal(r.bytes.length,original.bytes.length);assert.notEqual(r.sha256,original.sha256);assert.deepEqual(r.bytes,d);
 console.log('PRIVATE_NEW_VERSION_PASS: changed H3C version and rootfs payload; repaired FIT hashes; no catalog lookup');
})().catch(e=>{console.error(e);process.exitCode=1;});
