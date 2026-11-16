/* SPDX-License-Identifier: GPL-2.0-or-later. Inputs and outputs are private. */
const fs=require('node:fs'),path=require('node:path'),fw=require('../core.js');
(async()=>{
 const manifest=JSON.parse(fs.readFileSync(process.argv[2])),results=[];
 for(const x of manifest.inputs) {
  const row={group:x.group,name:path.basename(x.path)};
  try {
   const r=await fw.unpack(fs.readFileSync(x.path));const {bytes,...metadata}=r;
   const out=path.join(manifest.output,x.group,row.name+'.ubi');fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,bytes);
   Object.assign(row,{ok:true,output:out,...metadata});
  } catch(e) {Object.assign(row,{ok:false,error:e.message});}
  results.push(row); console.log(row.group,row.name,row.ok?row.sha256:row.error);
 }
 fs.writeFileSync(manifest.results,JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
