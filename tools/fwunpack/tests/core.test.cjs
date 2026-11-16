/* SPDX-License-Identifier: GPL-2.0-or-later */
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process'),crypto=require('node:crypto'),vm=require('node:vm');
const fw=require('../core.js'),f=require('./fixtures.cjs');
const cases={ubi:f.ubi,h3c:f.h3c(f.fit(f.ubi)),fit:f.fit(f.ubi),hdr1:f.hdr(f.ubi),jike:f.fit(f.ubi,{algo:'crc32',name:'ubi-jike-synthetic'}),ruijie:f.ruijie(f.fit(f.ubi)),'fit-offset':f.fit(f.ubi,{storage:'offset',algo:'sha1'}),'fit-position':f.fit(f.ubi,{storage:'position',algo:'crc32'}),'hdr1-fit':f.hdr(f.fit(f.ubi)),'tar-ubi':f.sysupgrade(f.ubi),'tar-fit':f.sysupgrade(f.fit(f.ubi)),sysupgrade:f.sysupgrade(),nested:f.h3c(f.fit(f.hdr(f.fit(f.ubi)),{name:'firmware'}))};
for(const [name,b] of Object.entries(cases)) test(name,async()=>{
  const r=await fw.unpack(b);assert.deepEqual(Buffer.from(r.bytes),f.ubi);assert.equal(r.sha256,crypto.createHash('sha256').update(f.ubi).digest('hex'));assert.equal(r.volumes.length,3);assert.ok(r.identity.configs.includes('config@mp02.1'));assert.ok(r.identity.compatible.includes('synthetic,router'));
});
for(const algo of ['crc32','sha1','sha256'])test('FIT '+algo+' mismatch',async()=>{const b=f.fit(f.ubi,{algo});const t=fw.fdt(b);t.root.children[0].children[0].children[0].props.value[0]^=1;await assert.rejects(fw.unpack(b),/hash/);});
for(const [name,b] of Object.entries(cases))test('truncate '+name,async()=>{for(const n of [0,3,39,55,159,511,Math.floor(b.length/2)])await assert.rejects(fw.unpack(b.subarray(0,n)));});
test('malicious containers',async()=>{
  const bad=[];
  let b=f.fit(f.ubi,{storage:'position'});fw.fdt(b).root.children[0].children[0].props['data-position'].fill(255);bad.push(b);
  b=f.fit(f.ubi);b.writeUInt32BE(0xffffffff,36);bad.push(b);
  b=f.hdr(f.ubi);b[100]^=1;bad.push(b);
  b=f.sysupgrade();b[148]^=1;bad.push(b);
  bad.push(f.tar({'sysupgrade-x/../root':f.ubi}));
  bad.push(f.fit(f.ubi,{extra:[f.node('rootfs',{data:f.ubi})]}));
  b=f.ubi;for(let n=0;n<10;n++)b=f.hdr(b);bad.push(b);
  bad.push(Buffer.from('HDR2 unsupported'));
  for(const x of bad)await assert.rejects(fw.unpack(x));
});
test('UBI validator rejects structural mutations',async()=>{
  for(const offset of [4,16,60,2048+60,4096+168,131072+4096+16,2*131072+4096]) {const b=Buffer.from(f.ubi);b[offset]^=1;assert.throws(()=>fw.validateUBI(b));}
  const b=Buffer.from(f.ubi);b.writeUInt32BE(0x7ffff000,2*131072+2048+8);b.writeUInt32BE(fw.crc32(b.subarray(2*131072+2048,2*131072+2048+60),true),2*131072+2048+60);assert.throws(()=>fw.validateUBI(b));
});
test('modified SquashFS metadata remains readable as UBI',async()=>{
  const b=Buffer.from(f.ubi),info=fw.validateUBI(b);const rootBlock=3*131072+4096;b[rootBlock+28]=0x99;const r=await fw.unpack(b);assert.equal(r.standardSquashFS,false);assert.match(r.identity.squashfs,/无法识别/);
});
test('model mismatch and capacity only warn',async()=>{
  const r=await fw.unpack(f.ubi,{target:{slots:[{name:'small',bytes:131072}],configs:['wrong'],compatible:['wrong,device']}});assert.ok(r.warnings.some(w=>w.includes('超出')));assert.ok(r.warnings.some(w=>w.includes('明显不符')));assert.ok(r.warnings.some(w=>w.includes('compatible')));
});
test('hash fallback known vectors and block boundaries',async()=>{
  const context={Uint8Array,Int32Array,Uint32Array,DataView,TextDecoder,TextEncoder,setTimeout};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../core.js'),'utf8'),context);
  for(const n of [0,3,55,56,63,64,65,100000]) {const b=Buffer.alloc(n,97);for(const a of ['sha1','sha256']) assert.equal(await context.FWUnpack.digest(b,a),crypto.createHash(a).update(b).digest('hex'));}
});
test('ubinize byte parity with host mtd-utils',()=>{
  const dir=fs.mkdtempSync(path.join(process.env.TMPDIR||os.tmpdir(),'fwunpack-ubinize-'));
  try {
    for(const len of [96,126976,126977,300000]) {
      const root=Buffer.alloc(len);root.write('hsqs');root.writeUInt16LE(4,28);root.writeBigUInt64LE(BigInt(len),40);fs.writeFileSync(path.join(dir,'kernel'),f.kernel);fs.writeFileSync(path.join(dir,'root'),root);
      fs.writeFileSync(path.join(dir,'ubi.cfg'),`[kernel]\nmode=ubi\nimage=${dir}/kernel\nvol_id=0\nvol_type=dynamic\nvol_name=kernel\n[rootfs]\nmode=ubi\nimage=${dir}/root\nvol_id=1\nvol_type=dynamic\nvol_name=rootfs\n[data]\nmode=ubi\nvol_id=2\nvol_size=126976\nvol_type=dynamic\nvol_name=rootfs_data\nvol_flags=autoresize\n`);
      cp.execFileSync(process.env.UBINIZE||'ubinize',['-p','131072','-m','2048','-s','2048','-O','2048','-e','0','-Q','0','-o',path.join(dir,'out.ubi'),path.join(dir,'ubi.cfg')],{stdio:'pipe'});
      assert.deepEqual(Buffer.from(fw.ubinize(f.kernel,root)),fs.readFileSync(path.join(dir,'out.ubi')));
    }
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
if(process.env.FWUNPACK_FIXTURES) {fs.mkdirSync(process.env.FWUNPACK_FIXTURES,{recursive:true});for(const [n,b]of Object.entries(cases))fs.writeFileSync(path.join(process.env.FWUNPACK_FIXTURES,n+'.bin'),b);fs.writeFileSync(path.join(process.env.FWUNPACK_FIXTURES,'corrupt.bin'),f.h3c(f.fit(f.ubi)).subarray(0,1000));}

test('new versions require no rule or catalog update',async()=>{
  const root=Buffer.from(f.root);root[10000]^=0x5a;
  const kernel=f.fdt(f.node('',{description:f.text('Linux-99.12.34 future-version')},[f.node('images'),f.node('configurations',{},[f.node('config@mp02.1')])]));
  const future=Buffer.from(fw.ubinize(kernel,root));assert.notDeepEqual(future,f.ubi);
  const h=f.h3c(f.fit(future));h.write('SYNTHETIC-V999R999',96);
  for(const b of [future,h,f.hdr(future),f.hdr(f.fit(future)),f.ruijie(f.fit(future)),f.sysupgrade(future),f.fit(future,{storage:'offset'})]) {
    const r=await fw.unpack(b);assert.deepEqual(Buffer.from(r.bytes),future);assert.notEqual(r.sha256,crypto.createHash('sha256').update(f.ubi).digest('hex'));assert.ok(r.identity.descriptions.some(s=>s.includes('99.12.34')));
  }
});

test('fwtool metadata and signature trailers',async()=>{
  for(const b of [f.fwtool(f.sysupgrade()),f.fwtool(f.fwtool(f.sysupgrade()),0),f.fwtool(f.ubi),f.fwtool(f.fit(f.ubi))]) assert.deepEqual(Buffer.from((await fw.unpack(b)).bytes),f.ubi);
  for(const offset of [-12,-1,4000]) {const b=f.fwtool(f.sysupgrade());b[offset<0?b.length+offset:offset]^=1;await assert.rejects(fw.unpack(b));}
});

test('CMOC and ELECOM structured wrappers',async()=>{
  for(const b of [f.cmoc(f.fit(f.ubi)),f.cmoc(f.fit(f.ubi),1152),f.elecom(f.fit(f.ubi))]) assert.deepEqual(Buffer.from((await fw.unpack(b)).bytes),f.ubi);
  for(const offset of [4,8,1100]) {const b=f.cmoc(f.fit(f.ubi));b[offset]^=1;await assert.rejects(fw.unpack(b));}
  const asus=Buffer.alloc(100);asus.writeUInt32BE(0x27051956);asus.write('imag',64);await assert.rejects(fw.unpack(asus),/ASUS eMMC/);
});

test('rescue upload limit is independent from the 116 MiB slot limit',()=>{
  assert.throws(()=>fw.validateUBI(new Uint8Array(80*1048576+131072)),/80 MiB/);
});

test('FIT with separate NOR SquashFS reports why there is no UBI',async()=>{
  const b=f.fdt(f.node('',{},[f.node('images',{},[f.node('hlos',{data:f.kernel}),f.node('rootfs',{data:f.root})])]));
  await assert.rejects(fw.unpack(b),/独立 SquashFS/);
});

test('old JDCloud eMMC FIT path is recognized but never exported',async()=>{
  const b=f.fdt(f.node('',{description:f.text('Flashing emmc')},[f.node('images',{},[f.node('hlos',{data:f.kernel}),f.node('rootfs',{data:f.root})])]));
  await assert.rejects(fw.unpack(b),/eMMC FIT 使用独立分区/);
});
