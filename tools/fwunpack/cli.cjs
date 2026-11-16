#!/usr/bin/env node
/* SPDX-License-Identifier: GPL-2.0-or-later */
const fs = require('node:fs');
const {unpack} = require('./core.js');
async function main() {
  const args=process.argv.slice(2), file=args.shift();
  if(!file || args.length>1) throw new Error('用法：node tools/fwunpack/cli.cjs 输入文件 [输出.ubi]');
  const r=await unpack(fs.readFileSync(file));
  const {bytes,...metadata}=r;
  if(args[0]) fs.writeFileSync(args[0],bytes,{flag:'wx'});
  console.log(JSON.stringify(metadata,null,2));
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
