/* SPDX-License-Identifier: GPL-2.0-or-later */
(() => {
  'use strict';
  const en=document.documentElement.getAttribute('data-site-lang')==='en';
  const tr=(zh,enText)=>en?enText:zh;
  const $=id=>document.getElementById(id), targets=JSON.parse($('fw-target-data').textContent);
  const file=$('fw-file'),select=$('fw-target'),status=$('fw-status'),panel=$('fw-result'),cancel=$('fw-cancel'),drop=$('fw-drop');
  let worker=null,downloadURL='',result=null,baseWarnings=[],generation=0;
  const size=n=>`${(n/1048576).toFixed(2)} MiB (${n.toLocaleString('en-US')} ${en?'bytes':'字节'})`;
  const target=()=>targets.find(t=>t.id===select.value);
  function clear() {if(downloadURL)URL.revokeObjectURL(downloadURL);downloadURL='';result=null;panel.hidden=true;$('fw-download').removeAttribute('href');}
  function stop() {generation++;if(worker)worker.terminate();worker=null;cancel.hidden=true;}
  function td(text,tag='td') {const e=document.createElement(tag);e.textContent=text;return e;}

  // core.js messages are Chinese and are matched against the Chinese original.
  const MESSAGES = new Map([
    ['长度或偏移越界：文件截断或结构损坏', 'Length or offset out of range: the file is truncated or the structure is damaged'],
    ['UBI CRC 不符', 'UBI CRC mismatch'],
    ['不是 FIT / FDT', 'Not a FIT / FDT'],
    ['FIT 头版本或总长度无效', 'Invalid FIT header version or total length'],
    ['FIT 数据块重叠或未对齐', 'FIT data blocks overlap or are misaligned'],
    ['FIT 保留内存表无效', 'Invalid FIT reserve memory table'],
    ['FIT 保留内存表重叠', 'FIT reserve memory table overlaps'],
    ['FIT 字符串越界', 'FIT string out of range'],
    ['FIT 字符串未终止或过长', 'FIT string is not terminated or is too long'],
    ['FIT 节点或深度超过上限', 'FIT node count or depth exceeds the limit'],
    ['FIT 重复节点', 'Duplicate FIT node'],
    ['FIT 根节点无效', 'Invalid FIT root node'],
    ['FIT 节点未配对', 'Unpaired FIT node'],
    ['FIT 属性过多或不在节点内', 'Too many FIT properties, or a property is outside a node'],
    ['FIT 重复属性', 'Duplicate FIT property'],
    ['FIT 未关闭的节点', 'Unclosed FIT node'],
    ['FIT token 无效', 'Invalid FIT token'],
    ['FIT token 越界', 'FIT token out of range'],
    ['FIT 缺少结束标记', 'FIT end marker missing'],
    ['FIT 外置 data 单元无效', 'Invalid FIT external data cell'],
    ['FIT data 存储方式冲突', 'Conflicting FIT data storage methods'],
    ['FIT 外置 data 缺少大小', 'FIT external data has no size'],
    ['FIT 外置 data 地址无效', 'Invalid FIT external data address'],
    ['FIT 外置 data 与头部重叠', 'FIT external data overlaps the header'],
    ['FIT 签名未验证；这里只校验段内的 hash。', 'FIT signatures are not verified; only the hashes inside the sections are checked.'],
    ['FIT hash 节点过多', 'Too many FIT hash nodes'],
    ['重复 hash 数据量超过上限', 'Repeated hash data exceeds the limit'],
    ['UBI 大小必须是 128 KiB 的整数倍，且不超过救援端上传上限 80 MiB', 'UBI size must be a multiple of 128 KiB and no more than the rescue upload limit of 80 MiB'],
    ['UBI EC 头或 NAND 几何不符（需 PEB 128 KiB / VID 2048 / data 4096）', 'UBI EC header or NAND geometry mismatch (PEB 128 KiB / VID 2048 / data 4096 required)'],
    ['UBI image_seq 不一致', 'UBI image_seq mismatch'],
    ['UBI VID 头无效', 'Invalid UBI VID header'],
    ['UBI VID 数据长度无效', 'Invalid UBI VID data length'],
    ['UBI layout 卷无效', 'Invalid UBI layout volume'],
    ['UBI 卷 ID 或 LEB 超限（不接受 fastmap）', 'UBI volume ID or LEB out of range (no fastmap support)'],
    ['UBI 两份卷表缺失或不一致', 'The two UBI volume tables are missing or differ'],
    ['UBI 空卷记录非零', 'An empty UBI volume record is not zeroed'],
    ['UBI 卷表几何或名称无效', 'Invalid UBI volume table geometry or name'],
    ['UBI 卷标志无效或多个自动扩展卷', 'Invalid UBI volume flags or more than one autoresize volume'],
    ['UBI 卷重名', 'Duplicate UBI volume name'],
    ['UBI 预留 PEB 超限', 'UBI reserved PEBs exceed the limit'],
    ['UBI 必须同时包含 kernel 和 rootfs / ubi_rootfs 卷', 'UBI must contain both kernel and rootfs / ubi_rootfs volumes'],
    ['UBI 卷块未定义、重复或超出预留范围', 'UBI volume block is undefined, duplicated, or beyond the reserved range'],
    ['UBI dynamic VID 字段无效', 'Invalid UBI dynamic VID fields'],
    ['UBI static VID 字段无效', 'Invalid UBI static VID fields'],
    ['UBI static used_ebs 不一致', 'UBI static used_ebs mismatch'],
    ['UBI 卷数据 CRC 不符', 'UBI volume data CRC mismatch'],
    ['UBI static 卷缺块', 'A UBI static volume is missing blocks'],
    ['UBI 内核 FIT 或根文件系统 SquashFS 魔数无效', 'Invalid UBI kernel FIT or root filesystem SquashFS magic'],
    ['UBI 内核 FIT 长度无效', 'Invalid UBI kernel FIT length'],
    ['UBI 内核或根文件系统缺少连续 LEB', 'UBI kernel or root filesystem is missing consecutive LEBs'],
    ['卷长度超限', 'Volume length exceeds the limit'],
    ['标准 SquashFS v4', 'Standard SquashFS v4'],
    ['无法识别（可能是厂商修改的 SquashFS）', 'Unrecognized (possibly a vendor-modified SquashFS)'],
    ['内核身份无法完整识别；UBI 结构校验已通过', 'Kernel identity could not be fully identified; UBI structure validation passed'],
    ['sysupgrade 的 kernel / root 必须是 FIT / SquashFS', 'sysupgrade kernel / root must be FIT / SquashFS'],
    ['只可为标准 SquashFS v4 的 sysupgrade 生成 UBI', 'UBI can only be generated from a sysupgrade with standard SquashFS v4'],
    ['sysupgrade 生成的 UBI 过大', 'The UBI generated from sysupgrade is too large'],
    ['tar 缺少双零结束块', 'tar is missing the two zero end blocks'],
    ['tar 条目过多', 'Too many tar entries'],
    ['tar 八进制字段无效', 'Invalid tar octal field'],
    ['tar 大小超限', 'tar size exceeds the limit'],
    ['tar 头校验和不符', 'tar header checksum mismatch'],
    ['tar 路径无效或重复', 'Invalid or duplicate tar path'],
    ['tar 只接受普通文件和目录', 'tar accepts only regular files and directories'],
    ['tar 包含多个 sysupgrade 目录', 'tar contains more than one sysupgrade directory'],
    ['不是完整的 OpenWrt sysupgrade tar', 'Not a complete OpenWrt sysupgrade tar'],
    ['tar 结束块后有无法识别的数据', 'Unrecognized data after the tar end blocks'],
    ['sysupgrade 缺少 CONTROL 或 root', 'sysupgrade is missing CONTROL or root'],
    ['HDR1 类型或签名偏移无效', 'Invalid HDR1 type or signature offset'],
    ['HDR1 整包 CRC 不符', 'HDR1 whole-image CRC mismatch'],
    ['HDR1 段重叠或越界', 'HDR1 sections overlap or are out of range'],
    ['HDR1 段魔数或大小无效', 'Invalid HDR1 section magic or size'],
    ['HDR1 已检查 CRC；未验证厂商 RSA 签名。', 'HDR1 CRC was checked; the vendor RSA signature was not verified.'],
    ['HDR1 没有唯一的系统段（root.ubi / rootfs / firmware）', 'HDR1 has no unique system section (root.ubi / rootfs / firmware)'],
    ['fwtool 尾部层数过多', 'Too many fwtool trailer layers'],
    ['fwtool 尾部长度或类型无效', 'Invalid fwtool trailer length or type'],
    ['重复校验数据量超过上限', 'Repeated verification data exceeds the limit'],
    ['fwtool 尾部 CRC 不符', 'fwtool trailer CRC mismatch'],
    ['fwtool 元数据版本无效', 'Invalid fwtool metadata version'],
    ['fwtool 签名尾部已检查 CRC；未验证发布者签名。', 'The fwtool signature trailer CRC was checked; the publisher signature was not verified.'],
    ['ELECOM 产品头 (56)', 'ELECOM product header (56)'],
    ['CMOC (MSTC) 头', 'CMOC (MSTC) header'],
    ['H3C 头 (0xa0)', 'H3C header (0xa0)'],
    ['锐捷头 (0x800)', 'Ruijie header (0x800)'],
    ['小米 HDR1', 'Xiaomi HDR1'],
    ['裸 UBI', 'Raw UBI'],
    ['容器嵌套深度或候选段超过上限', 'Container nesting depth or number of candidate sections exceeds the limit'],
    ['小米 HDR2 尚未用真实样本验证，不能拆包', 'Xiaomi HDR2 has not been verified with a real sample and cannot be unpacked'],
    ['无法识别容器，或其中没有可用的 UBI；不支持 NOR / eMMC 系统包', 'The container could not be identified, or it has no usable UBI; NOR / eMMC system images are not supported'],
    ['ASUS eMMC 包使用独立内核 / rootfs 分区，不含本工具可输出的 UBI；该规则未用真实样本验证', 'ASUS eMMC images use separate kernel / rootfs partitions and contain no UBI this tool can output; this rule has not been verified with a real sample'],
    ['ELECOM 产品头后没有 CMOC', 'No CMOC follows the ELECOM product header'],
    ['CMOC 长度字段或 FIT 偏移无效', 'Invalid CMOC length field or FIT offset'],
    ['CMOC payload CRC 不符', 'CMOC payload CRC mismatch'],
    ['锐捷头长度字段无效', 'Invalid Ruijie header length field'],
    ['厂商头后没有 FIT', 'No FIT follows the vendor header'],
    ['sysupgrade 缺少 kernel', 'sysupgrade is missing kernel'],
    ['由 sysupgrade 生成 UBI：PEB 128 KiB、页 2048、LEB 126976；只适用于相同 NAND 几何与 kernel/rootfs 卷启动方式。', 'UBI generated from sysupgrade: PEB 128 KiB, page 2048, LEB 126976; only for the same NAND geometry and kernel/rootfs volume boot layout.'],
    ['ubinize (kernel + rootfs + rootfs_data 自动扩展)', 'ubinize (kernel + rootfs + rootfs_data autoresize)'],
    ['FIT 缺少 /images', 'FIT is missing /images'],
    ['FIT image 数据段重叠', 'FIT image data sections overlap'],
    ['QSDK eMMC FIT 使用独立分区，没有 UBI（旧京东云解析路径；未用真实样本验证）', 'QSDK eMMC FIT uses separate partitions and has no UBI (old JD Cloud parsing path; not verified with a real sample)'],
    ['FIT 有多个系统候选段，无法安全选择', 'FIT has more than one system candidate section and cannot be selected safely'],
    ['FIT 使用独立 SquashFS rootfs 段，没有 UBI；不能将未知启动布局合成为 UBI', 'FIT uses a separate SquashFS rootfs section and has no UBI; a UBI cannot be synthesized from an unknown boot layout'],
    ['FIT 没有 UBI 系统段；可能是独立内核或 eMMC 包', 'FIT has no UBI system section; it may be a separate-kernel or eMMC image'],
    ['尚未选择目标机型；未检查系统槽容量和机型。', 'No target model selected; system slot size and model were not checked.'],
    ['该机型系统槽大小不确定，请在救援页核对分区容量。', 'The system slot size for this model is uncertain; check the partition size in the rescue page.'],
    ['镜像或卷预留空间超出所选机型的系统槽；救援页会拒绝容量不足的目标。', 'The image or reserved volume space exceeds the system slot of the selected model; the rescue page rejects targets that are too small.'],
    ['镜像只放得进这些布局：', 'The image fits only these layouts: '],
    ['此镜像含原厂 wifi_fw / bt_fw 卷。H3C 救援页只允许把它刷入原厂双系统布局；单系统布局会拒绝，请先恢复双系统分区表。', 'This image contains stock wifi_fw / bt_fw volumes. The H3C rescue page allows flashing it only into the stock dual system layout; a single system layout is rejected. Restore the dual system partition table first.'],
    ['内核 FIT config 与目标机型明显不符。刷错可能无法启动；可回救援页重新刷入正确 UBI。', 'The kernel FIT config clearly does not match the target model. A wrong flash may fail to boot; return to the rescue page and flash the correct UBI.'],
    ['内核 DTB compatible 与目标机型不符。刷错可能无法启动；可回救援页重刷。', 'The kernel DTB compatible does not match the target model. A wrong flash may fail to boot; return to the rescue page and flash again.'],
    ['请选择非空且不超过 256 MiB 的固件', 'Select a non-empty firmware file no larger than 256 MiB'],
    ['结构通过不代表机型适配。实际可写容量还取决于坏块和救援页当前布局；请以救援页校验结果为准。', 'Passing structure validation does not mean the model is compatible. The writable capacity also depends on bad blocks and the current rescue page layout; follow the rescue page validation result.'],
  ]);

  // Messages built with variables. Each regex captures the variable parts.
  const PATTERNS = [
    [/^不支持的 FIT hash 算法：(.*)$/, 'Unsupported FIT hash algorithm: $1'],
    [/^FIT hash 不符：(.*) \/ (.*)$/, 'FIT hash mismatch: $1 / $2'],
    [/^FIT 有 (\d+) 个 image 没有 hash 节点；不能验证这些段的完整性。$/, '$1 FIT images have no hash node; the integrity of those sections cannot be verified.'],
    [/^镜像只放得进这些布局：(.*)。请先在救援页核对当前布局。$/, m => `The image fits only these layouts: ${m[1].replace(/、/g, ', ')}. Check the current layout in the rescue page first.`],
  ];

  function coreText(message) {
    if (!en || typeof message !== 'string') return message;
    if (MESSAGES.has(message)) return MESSAGES.get(message);
    for (const [re, replacement] of PATTERNS) {
      const m = re.exec(message);
      if (m) return typeof replacement === 'function' ? replacement(m) : replacement.replace(/\$(\d)/g, (_, i) => m[Number(i)]);
    }
    return message;
  }

  function warnings() {
    $('fw-target-note').textContent=target()?.source || tr('系统槽容量以救援页实际分区表为准。','System slot sizes follow the actual partition table in the rescue page.');
    if(!result)return;
    const rows=[...baseWarnings,...FWUnpack.targetWarnings(result,target())];$('fw-warnings').replaceChildren(...rows.map(w=>td(coreText(w),'li')));
  }
  select.addEventListener('change',warnings);
  async function load(f) {
    stop();clear();const ticket=generation;
    if(!f)return;$('fw-filename').textContent=f.name;
    if(f.size===0||f.size>FWUnpack.MAX_INPUT) {status.textContent=tr('请选择非空且不超过 256 MiB 的固件。','Select a non-empty firmware file no larger than 256 MiB.');return;}
    status.textContent=tr('正在读取 ','Reading ')+f.name+' …';cancel.hidden=false;
    try {
      const buffer=await f.arrayBuffer();if(ticket!==generation)return;
      // Inline factory in a Blob worker: no fetch/importScripts, works on file://.
      const source=FWUnpackFactory.toString()+`\nonmessage=async e=>{try{const r=await FWUnpackFactory().unpack(e.data);r.bytes=r.bytes.slice();postMessage({result:r},[r.bytes.buffer]);}catch(error){postMessage({error:error.message});}};`;
      const workerURL=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
      worker=new Worker(workerURL);URL.revokeObjectURL(workerURL);
      status.textContent=tr('正在本机校验并拆包 ','Validating and unpacking locally ')+f.name+' …';
      worker.onerror=()=>{if(ticket!==generation)return;stop();clear();status.textContent=tr('浏览器无法运行本地处理线程。请使用支持 Web Worker 的新版浏览器，并完整保存本站文件。','The browser cannot start a local processing thread. Use a newer browser with Web Worker support and save all site files.');};
      worker.onmessage=e=>{
        if(ticket!==generation)return;stop();
        if(e.data.error) {clear();status.textContent=tr('无法生成 UBI：','Could not generate UBI: ')+coreText(e.data.error);return;}
        result=e.data.result;baseWarnings=result.warnings.filter(w=>!w.startsWith('尚未选择目标机型'));
        $('fw-chain').textContent=result.chain.join('\n  → ');
        const identity=result.identity,details=[[tr('文件','File'),f.name],[tr('UBI 大小','UBI size'),size(result.size)],['SHA-256',result.sha256],
          [tr('NAND 几何','NAND geometry'),`PEB ${result.pebSize} / LEB ${result.lebSize} / `+tr('页 ','Page ')+result.pageSize+' '+tr('字节','bytes')],
          [tr('系统身份','System identity'),identity.descriptions.join(' / ')||tr('无法识别','Unrecognized')],['FIT config',identity.configs.join(', ')||tr('无法识别','Unrecognized')],['DTB compatible',identity.compatible.join(', ')||tr('无法识别','Unrecognized')],[tr('根文件系统','Root filesystem'),coreText(identity.squashfs)]];
        $('fw-details').replaceChildren(...details.map(([a,b])=>{const trEl=document.createElement('tr');trEl.append(td(a,'th'),td(b));return trEl;}));
        $('fw-volumes').replaceChildren(...result.volumes.map(v=>{const trEl=document.createElement('tr');trEl.append(...[`${v.id}: ${v.name}`,v.type,size(v.bytes),String(v.writtenLEBs),v.flags&1?tr('自动扩展','autoresize'):'—'].map(x=>td(x)));return trEl;}));
        downloadURL=URL.createObjectURL(new Blob([result.bytes],{type:'application/octet-stream'}));
        const link=$('fw-download');link.href=downloadURL;link.download=f.name.replace(/[<>:"/\\|?*\x00-\x1f]/g,'_')+'.'+result.sha256.slice(0,12)+'.ubi';
        status.textContent=tr('已拆出 UBI，结构校验通过。请核对下方机型和容量提示。','UBI extracted and structure validated. Check the model and size notes below.');panel.hidden=false;warnings();
      };
      worker.postMessage(buffer,[buffer]);
    } catch(e) {if(ticket!==generation)return;stop();clear();status.textContent=tr('无法读取或处理文件：','Could not read or process the file: ')+coreText(e.message);}
  }
  $('fw-browse').addEventListener('click',()=>file.click());
  file.addEventListener('change',()=>load(file.files[0]));
  cancel.addEventListener('click',()=>{stop();clear();file.value='';$('fw-filename').textContent=tr('未选择文件','No file selected');status.textContent=tr('已取消，可以重新选择文件。','Canceled. Select another file.');});
  drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('dragover');});
  drop.addEventListener('dragleave',()=>drop.classList.remove('dragover'));
  drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('dragover');if(e.dataTransfer.files.length!==1){status.textContent=tr('请一次拖入一个文件。','Drop one file at a time.');return;}file.value='';load(e.dataTransfer.files[0]);});
  window.addEventListener('pagehide',()=>{stop();clear();});
})();
