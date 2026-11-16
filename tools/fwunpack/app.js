/* SPDX-License-Identifier: GPL-2.0-or-later */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), targets=JSON.parse($('fw-target-data').textContent);
  const file=$('fw-file'),select=$('fw-target'),status=$('fw-status'),panel=$('fw-result'),cancel=$('fw-cancel'),drop=$('fw-drop');
  let worker=null,downloadURL='',result=null,baseWarnings=[],generation=0;
  const size=n=>`${(n/1048576).toFixed(2)} MiB (${n.toLocaleString('en-US')} 字节)`;
  const target=()=>targets.find(t=>t.id===select.value);
  function clear() {if(downloadURL)URL.revokeObjectURL(downloadURL);downloadURL='';result=null;panel.hidden=true;$('fw-download').removeAttribute('href');}
  function stop() {generation++;if(worker)worker.terminate();worker=null;cancel.hidden=true;}
  function td(text,tag='td') {const e=document.createElement(tag);e.textContent=text;return e;}
  function warnings() {
    $('fw-target-note').textContent=target()?.source || '系统槽容量以救援页实际分区表为准。';
    if(!result)return;
    const rows=[...baseWarnings,...FWUnpack.targetWarnings(result,target())];$('fw-warnings').replaceChildren(...rows.map(w=>td(w,'li')));
  }
  select.addEventListener('change',warnings);
  async function load(f) {
    stop();clear();const ticket=generation;
    if(!f)return;$('fw-filename').textContent=f.name;
    if(f.size===0||f.size>FWUnpack.MAX_INPUT) {status.textContent='请选择非空且不超过 256 MiB 的固件。';return;}
    status.textContent='正在读取 '+f.name+' …';cancel.hidden=false;
    try {
      const buffer=await f.arrayBuffer();if(ticket!==generation)return;
      // Inline factory in a Blob worker: no fetch/importScripts, works on file://.
      const source=FWUnpackFactory.toString()+`\nonmessage=async e=>{try{const r=await FWUnpackFactory().unpack(e.data);r.bytes=r.bytes.slice();postMessage({result:r},[r.bytes.buffer]);}catch(error){postMessage({error:error.message});}};`;
      const workerURL=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
      worker=new Worker(workerURL);URL.revokeObjectURL(workerURL);
      status.textContent='正在本机校验并拆包 '+f.name+' …';
      worker.onerror=()=>{if(ticket!==generation)return;stop();clear();status.textContent='浏览器无法运行本地处理线程。请使用支持 Web Worker 的新版浏览器，并完整保存本站文件。';};
      worker.onmessage=e=>{
        if(ticket!==generation)return;stop();
        if(e.data.error) {clear();status.textContent='无法生成 UBI：'+e.data.error;return;}
        result=e.data.result;baseWarnings=result.warnings.filter(w=>!w.startsWith('尚未选择目标机型'));
        $('fw-chain').textContent=result.chain.join('\n  → ');
        const identity=result.identity,details=[['文件',f.name],['UBI 大小',size(result.size)],['SHA-256',result.sha256],
          ['NAND 几何',`PEB ${result.pebSize} / LEB ${result.lebSize} / 页 ${result.pageSize} 字节`],
          ['系统身份',identity.descriptions.join(' / ')||'无法识别'],['FIT config',identity.configs.join(', ')||'无法识别'],['DTB compatible',identity.compatible.join(', ')||'无法识别'],['根文件系统',identity.squashfs]];
        $('fw-details').replaceChildren(...details.map(([a,b])=>{const tr=document.createElement('tr');tr.append(td(a,'th'),td(b));return tr;}));
        $('fw-volumes').replaceChildren(...result.volumes.map(v=>{const tr=document.createElement('tr');tr.append(...[`${v.id}: ${v.name}`,v.type,size(v.bytes),String(v.writtenLEBs),v.flags&1?'自动扩展':'—'].map(x=>td(x)));return tr;}));
        downloadURL=URL.createObjectURL(new Blob([result.bytes],{type:'application/octet-stream'}));
        const link=$('fw-download');link.href=downloadURL;link.download=f.name.replace(/[<>:"/\\|?*\x00-\x1f]/g,'_')+'.'+result.sha256.slice(0,12)+'.ubi';
        status.textContent='已拆出 UBI，结构校验通过。请核对下方机型和容量提示。';panel.hidden=false;warnings();
      };
      worker.postMessage(buffer,[buffer]);
    } catch(e) {if(ticket!==generation)return;stop();clear();status.textContent='无法读取或处理文件：'+e.message;}
  }
  $('fw-browse').addEventListener('click',()=>file.click());
  file.addEventListener('change',()=>load(file.files[0]));
  cancel.addEventListener('click',()=>{stop();clear();file.value='';$('fw-filename').textContent='未选择文件';status.textContent='已取消，可以重新选择文件。';});
  drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('dragover');});
  drop.addEventListener('dragleave',()=>drop.classList.remove('dragover'));
  drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('dragover');if(e.dataTransfer.files.length!==1){status.textContent='请一次拖入一个文件。';return;}file.value='';load(e.dataTransfer.files[0]);});
  window.addEventListener('pagehide',()=>{stop();clear();});
})();
