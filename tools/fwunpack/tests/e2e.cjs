/* SPDX-License-Identifier: GPL-2.0-or-later. Run only on a host with Chromium. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process'),{pathToFileURL}=require('node:url');
(async()=>{
 const out=process.env.OUT;if(!out)throw Error('OUT is required');
 for(const [key,name]of [['TMPDIR','tmp'],['XDG_CONFIG_HOME','browser-config'],['XDG_CACHE_HOME','browser-cache'],['XDG_RUNTIME_DIR','browser-runtime']]) {const dir=path.join(out,name);fs.mkdirSync(dir,{recursive:true,mode:0o700});process.env[key]=dir;}
 const fixtures=process.env.FWUNPACK_FIXTURES||path.join(out,'synthetic'),downloads=path.join(out,'downloads'),screens=path.join(out,'screenshots');for(const p of [downloads,screens])fs.mkdirSync(p,{recursive:true});
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM,headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({acceptDownloads:true,offline:true,viewport:{width:1360,height:1000}}),page=await context.newPage(),errors=[],network=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
 const url=pathToFileURL(path.resolve('site/dist/tools/fwunpack.html')).href;
 const tests=['h3c','fit','hdr1','jike','ubi','sysupgrade'].map(n=>({name:'synthetic-'+n,path:path.join(fixtures,n+'.bin')}));
 if(process.env.FWUNPACK_E2E_MANIFEST) {
  const m=JSON.parse(fs.readFileSync(process.env.FWUNPACK_E2E_MANIFEST));
  for(const group of ['h3c','xiaomi','jike','ruijie','nx54']) {const x=m.inputs.find(x=>x.group===group&&(group!=='xiaomi'||x.path.endsWith('.bin')));if(x)tests.push({name:'private-'+group,path:x.path});}
  const bare=m.inputs.find(x=>x.group==='xiaomi'&&x.path.endsWith('.ubi'));if(bare)tests.push({name:'private-bare-ubi',path:bare.path});
  const x=m.inputs.find(x=>x.group==='download'&&x.path.includes('b3000-4.5.22'));if(x)tests.push({name:'private-glinet',path:x.path});
 }
 const results=[];
 try {
  await page.goto(url);await page.waitForFunction(()=>!!globalThis.FWUnpack);if(!await page.evaluate(()=>JSON.parse(document.getElementById('fw-target-data').textContent).every(t=>t.configs.length>0)))throw Error('model DTS config mapping missing');await page.screenshot({path:path.join(screens,'fwunpack-empty.png'),fullPage:true});
  for(const x of tests) {
   await page.locator('#fw-file').setInputFiles(x.path);await page.waitForFunction(()=>!document.getElementById('fw-result').hidden,{},{timeout:120000});
   const expected=JSON.parse(cp.execFileSync('node',['tools/fwunpack/cli.cjs',x.path],{maxBuffer:2*1024*1024,timeout:120000}));
   const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#fw-download').click()]);
   const dest=path.join(downloads,x.name+'.ubi');await download.saveAs(dest);const sha=crypto.createHash('sha256').update(fs.readFileSync(dest)).digest('hex');
   if(sha!==expected.sha256)throw Error('download mismatch '+x.name);
   if(!download.suggestedFilename().includes(sha.slice(0,12)))throw Error('filename missing digest');
   results.push({name:x.name,sha256:sha,bytes:expected.size});
   if(x.name==='private-h3c'||x.name==='synthetic-h3c') {await page.locator('#fw-target').selectOption('h3c-rt3000');await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(screens,x.name+'.png'),fullPage:true});}
  }
  await page.locator('#fw-file').setInputFiles(path.join(fixtures,'corrupt.bin'));
  await page.waitForFunction(()=>document.getElementById('fw-status').textContent.includes('无法生成'));
  if(!await page.locator('#fw-result').isHidden()||await page.locator('#fw-download').getAttribute('href'))throw Error('stale download after failure');
  await page.screenshot({path:path.join(screens,'fwunpack-corrupt.png'),fullPage:true});
  // Drag-and-drop follows the same extraction path.
  const bytes=Array.from(fs.readFileSync(path.join(fixtures,'ubi.bin')));
  await page.evaluate(bytes=>{const d=new DataTransfer();d.items.add(new File([new Uint8Array(bytes)],'drag.ubi'));document.getElementById('fw-drop').dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:d}));},bytes);
  await page.waitForFunction(()=>!document.getElementById('fw-result').hidden);
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(screens,'fwunpack-mobile.png'),fullPage:true});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('horizontal overflow on mobile');
  // Begin a new read, cancel it, then ensure a later file can finish.
  await page.evaluate(()=>{const d=new DataTransfer();d.items.add(new File([new Uint8Array(100*1048576)],'cancel-large.bin'));const f=document.getElementById('fw-file');f.files=d.files;f.dispatchEvent(new Event('change'));document.getElementById('fw-cancel').click();});
  if(!await page.locator('#fw-result').isHidden())throw Error('cancel left stale result');
  await page.locator('#fw-file').setInputFiles(path.join(fixtures,'ubi.bin'));await page.waitForFunction(()=>!document.getElementById('fw-result').hidden);
  if(process.env.FWUNPACK_LARGE) {
    await page.setViewportSize({width:1360,height:1000});const started=Date.now();
    await page.locator('#fw-file').setInputFiles(process.env.FWUNPACK_LARGE);await page.waitForFunction(()=>!document.getElementById('fw-result').hidden,{},{timeout:120000});
    const [d]=await Promise.all([page.waitForEvent('download'),page.locator('#fw-download').click()]);const dest=path.join(downloads,'large.ubi');await d.saveAs(dest);
    const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');const expected=JSON.parse(cp.execFileSync('node',['tools/fwunpack/cli.cjs',process.env.FWUNPACK_LARGE],{timeout:120000}));if(sha(dest)!==expected.sha256)throw Error('100 MiB container mismatch');
    results.push({name:'100-MiB-container',milliseconds:Date.now()-started,bytes:fs.statSync(dest).size});
  }
  if(network.length||errors.length)throw Error(JSON.stringify({network,errors}));
  fs.writeFileSync(path.join(out,'results/e2e.json'),JSON.stringify({cases:results,corrupt:true,drag:true,cancel:true,mobile:true,network,errors},null,2));
  console.log('E2E_PASS',results.length,'downloads; corrupt, drop, cancel, mobile; zero HTTP requests; file:// offline');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
