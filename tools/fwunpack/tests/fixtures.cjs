/* SPDX-License-Identifier: GPL-2.0-or-later
 * Every byte here is synthetic. Never copy proprietary input into fixtures.
 */
const crypto=require('node:crypto'),fw=require('../core.js');
const B=x=>Buffer.from(x),be=n=>{const b=Buffer.alloc(4);b.writeUInt32BE(n>>>0);return b;};
const pad=b=>Buffer.concat([b,Buffer.alloc((4-b.length%4)%4)]);
const text=s=>B(s+'\0');
function node(name,props={},children=[]) {return {name,props,children};}
function fdt(root) {
  const names=[],chunks=[];
  function add(n) {
    chunks.push(be(1),pad(text(n.name)));
    for(const [k,v] of Object.entries(n.props)) {let offset=names.join('').length;if(!names.includes(k+'\0')) names.push(k+'\0');else offset=names.join('').indexOf(k+'\0');chunks.push(be(3),be(v.length),be(offset),pad(B(v)));}
    for(const c of n.children)add(c);chunks.push(be(2));
  }
  add(root);chunks.push(be(9));const s=Buffer.concat(chunks),strings=B(names.join('')),head=Buffer.alloc(56);
  [0xd00dfeed,56+s.length+strings.length,56,56+s.length,40,17,16,0,strings.length,s.length].forEach((v,i)=>head.writeUInt32BE(v,i*4));return Buffer.concat([head,s,strings]);
}
function fit(data,{storage='inline',algo='sha256',name='ubi-synthetic',extra=[]}={}) {
  const hash=algo==='crc32'?be(fw.crc32(data)):crypto.createHash(algo).update(data).digest();
  const props=storage==='inline'?{data:B(data)}:{'data-size':be(data.length),[storage==='offset'?'data-offset':'data-position']:be(0)};
  const n=node(name,props,[node('hash@1',{algo:text(algo),value:hash})]),root=node('',{},[node('images',{},[n,...extra])]);
  let t=fdt(root);
  if(storage!=='inline') {const base=Math.ceil(t.length/4)*4;if(storage==='position'){props['data-position']=be(base);t=fdt(root);}return Buffer.concat([t,Buffer.alloc(base-t.length),B(data)]);}
  return t;
}
const dt=fdt(node('',{compatible:text('synthetic,router\0qcom,ipq5018')}));
const kernel=fdt(node('',{description:text('Linux-6.6.99 synthetic')},[node('images',{},[node('kernel-1',{description:text('Linux-6.6.99'),data:B('synthetic-kernel'),type:text('kernel')}),node('fdt-1',{data:dt,type:text('flat_dt'),compression:text('none')})]),node('configurations',{},[node('config@mp02.1')])]));
const root=Buffer.alloc(300000,0);root.write('hsqs');root.writeUInt16LE(4,28);root.writeBigUInt64LE(BigInt(root.length),40);
const ubi=B(fw.ubinize(kernel,root));
function h3c(b) {const h=Buffer.alloc(160);h.write('H3C_');return Buffer.concat([h,B(b)]);}
function ruijie(b) {const h=Buffer.alloc(2048);h.writeUInt32BE(0x12468ace);h.writeUInt32BE(0xce8a4612,4);h.writeUInt32BE(2048,8);return Buffer.concat([h,B(b)]);}
function hdr(b) {
  const head=Buffer.alloc(56),s=Buffer.alloc(48);head.write('HDR1');head.writeUInt32LE(56+48+b.length,4);head.writeUInt32LE(56,16);head.writeUInt16LE(0x33,14);
  s.writeUInt16LE(0xbabe);s.writeUInt32LE(b.length,8);s.write('root.ubi',16);const result=Buffer.concat([head,s,B(b),Buffer.alloc(16)]);result.writeUInt32LE(fw.crc32(result.subarray(12),true),8);return result;
}
function tar(entries) {
  const out=[];
  for(const [name,d] of Object.entries(entries)) {
    const b=B(d),h=Buffer.alloc(512);h.write(name);h.write('0000644\0',100);h.write('0000000\0',108);h.write('0000000\0',116);h.write(b.length.toString(8).padStart(11,'0')+'\0',124);h.write('00000000000\0',136);h.fill(32,148,156);h[156]=48;h.write('ustar\0',257);h.write('00',263);const sum=h.reduce((a,v)=>a+v,0);h.write(sum.toString(8).padStart(6,'0')+'\0 ',148);out.push(h,b,Buffer.alloc((512-b.length%512)%512));
  }
  return Buffer.concat([...out,Buffer.alloc(1024)]);
}
const sysupgrade=(r=root)=>tar({'sysupgrade-synthetic/CONTROL':B('BOARD=synthetic\n'),'sysupgrade-synthetic/kernel':kernel,'sysupgrade-synthetic/root':r});
module.exports={B,be,text,node,fdt,fit,kernel,root,ubi,h3c,hdr,ruijie,tar,sysupgrade};
function fwtool(b,type=1) {
  const data=type===1?Buffer.concat([Buffer.alloc(8),B('{"supported_devices":["synthetic,router"]}')]):B('synthetic signature');
  const prefix=Buffer.concat([B(b),data]),t=Buffer.alloc(16);t.write('FWx0');t.writeUInt32BE(fw.crc32(prefix,true),4);t[8]=type;t.writeUInt32BE(data.length+16,12);return Buffer.concat([prefix,t]);
}
module.exports.fwtool=fwtool;

function cmoc(b,header=1024) {const h=Buffer.alloc(header);h.write('CMOC');h.writeUInt32LE(b.length,4);h.writeUInt32LE(fw.crc32(b),8);return Buffer.concat([h,B(b)]);}
function elecom(b) {const h=Buffer.alloc(56);h.write('ELECOM');return Buffer.concat([h,cmoc(b)]);}
module.exports.cmoc=cmoc;module.exports.elecom=elecom;
