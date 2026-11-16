/* SPDX-License-Identifier: GPL-2.0-or-later
 * Offline UBI extraction. No I/O, network, eval, decompression or vendor code.
 * Classic script + CommonJS intentionally allow saved pages to run on file://.
 */
function FWUnpackFactory() {
  'use strict';
  const PEB = 131072, PAGE = 2048, DATA = 4096, LEB = PEB - DATA;
  const LAYOUT = 0x7fffefff, MAX_PEBS = 928, MAX_INPUT = 256 * 1024 * 1024, MAX_UBI = 80 * 1024 * 1024;
  const fail = (s) => { throw new Error(s); };
  const need = (c, s) => { if (!c) fail(s); };
  function range(b, o, n) {
    need(Number.isSafeInteger(o) && Number.isSafeInteger(n) && o >= 0 && n >= 0 && o <= b.length && n <= b.length - o, '长度或偏移越界：文件截断或结构损坏');
    return b.subarray(o, o + n);
  }
  const view = b => new DataView(b.buffer, b.byteOffset, b.byteLength);
  function u32(b, o = 0, le = false) { range(b, o, 4); return view(b).getUint32(o, le); }
  function u16(b, o, le = false) { range(b, o, 2); return view(b).getUint16(o, le); }
  function u64(b, o, le = false) {
    const lo = u32(b, o + (le ? 0 : 4), le), hi = u32(b, o + (le ? 4 : 0), le);
    const n = hi * 4294967296 + lo; return Number.isSafeInteger(n) ? n : Infinity;
  }
  const put = (b, o, n) => view(b).setUint32(o, n, false);
  const str = b => new TextDecoder().decode(b);
  function cstr(b, o = 0, limit = b.length - o) {
    const s = range(b, o, limit), end = s.indexOf(0); return str(end < 0 ? s : s.subarray(0, end));
  }
  const magic = (b, s) => b.length >= s.length && Array.from(s).every((c, i) => b[i] === c.charCodeAt(0));
  const equal = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
  const all = (b, v) => b.every(x => x === v);
  const hex = b => Array.from(b, x => x.toString(16).padStart(2, '0')).join('');
  const crcTable = Uint32Array.from({length: 256}, (_, n) => {
    for (let j = 0; j < 8; j++) n = (n >>> 1) ^ ((n & 1) ? 0xedb88320 : 0); return n >>> 0;
  });
  function crc32(b, raw = false) {
    let c = 0xffffffff; for (const v of b) c = (c >>> 8) ^ crcTable[(c ^ v) & 255];
    return (raw ? c : c ^ 0xffffffff) >>> 0;
  }
  function crcOK(b, len) { need(crc32(range(b, 0, len), true) === u32(b, len), 'UBI CRC 不符'); }

  // SHA-256 fallback reused from tools/bootbridge/web/site/assets/engine.js.
  var K = new Int32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);

  function Sha256() {
    this.h = new Int32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
    this.w = new Int32Array(64); this.buf = new Uint8Array(64); this.used = 0; this.len = 0;
  }
  Sha256.prototype.block = function (p, o) {
    var w = this.w, h = this.h, i, a, b, c, d, e, f, g, hh, t1, t2, x, y;
    for (i = 0; i < 16; i++) w[i] = (p[o + 4 * i] << 24) | (p[o + 4 * i + 1] << 16) | (p[o + 4 * i + 2] << 8) | p[o + 4 * i + 3];
    for (i = 16; i < 64; i++) {
      x = w[i - 15]; y = w[i - 2];
      w[i] = (((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3)) + w[i - 16] +
             (((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10)) + w[i - 7] | 0;
    }
    a = h[0]; b = h[1]; c = h[2]; d = h[3]; e = h[4]; f = h[5]; g = h[6]; hh = h[7];
    for (i = 0; i < 64; i++) {
      t1 = hh + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + K[i] + w[i] | 0;
      t2 = (((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c)) | 0;
      hh = g; g = f; f = e; e = d + t1 | 0; d = c; c = b; b = a; a = t1 + t2 | 0;
    }
    h[0] = h[0] + a | 0; h[1] = h[1] + b | 0; h[2] = h[2] + c | 0; h[3] = h[3] + d | 0;
    h[4] = h[4] + e | 0; h[5] = h[5] + f | 0; h[6] = h[6] + g | 0; h[7] = h[7] + hh | 0;
  };
  Sha256.prototype.update = function (u8) {
    var n = u8.length, o = 0, z;
    this.len += n;
    if (this.used) {
      z = Math.min(64 - this.used, n); this.buf.set(u8.subarray(0, z), this.used); this.used += z; o = z;
      if (this.used < 64) return this;
      this.block(this.buf, 0); this.used = 0;
    }
    for (; o + 64 <= n; o += 64) this.block(u8, o);
    if (o < n) { this.buf.set(u8.subarray(o), 0); this.used = n - o; }
    return this;
  };
  Sha256.prototype.hex = function () {
    var bits = this.len * 8, pad = new Uint8Array(((this.used < 56) ? 56 : 120) - this.used + 8), i, s = '', v;
    pad[0] = 0x80;
    for (i = 0; i < 8; i++) { pad[pad.length - 1 - i] = bits % 256; bits = Math.floor(bits / 256); }
    this.update(pad);
    for (i = 0; i < 8; i++) { v = this.h[i] >>> 0; s += ('0000000' + v.toString(16)).slice(-8); }
    return s;
  };

  function toHex(buf) {
    var u = new Uint8Array(buf), s = '', i;
    for (i = 0; i < u.length; i++) s += (u[i] < 16 ? '0' : '') + u[i].toString(16);
    return s;
  }
  function subtle() {
    var c = (typeof self !== 'undefined' && self.crypto) || (typeof globalThis !== 'undefined' && globalThis.crypto);
    return c && c.subtle && typeof c.subtle.digest === 'function' ? c.subtle : null;
  }
  var tick = function () { return new Promise(function (r) { setTimeout(r, 0); }); };

  /* sha256(u8, {onProgress(fraction), pureJs}) -> Promise<hex> */
  function sha256(u8, opt) {
    opt = opt || {};
    var s = !opt.pureJs && subtle();
    if (s) {
      return s.digest('SHA-256', u8).then(toHex, function () { return sha256(u8, { onProgress: opt.onProgress, pureJs: true }); });
    }
    var h = new Sha256(), step = 4 << 20, o = 0;
    return new Promise(function (resolve, reject) {
      (function next() {
        try {
          var end = Math.min(o + step, u8.length);
          h.update(u8.subarray(o, end)); o = end;
          if (opt.onProgress) opt.onProgress(u8.length ? o / u8.length : 1);
          if (o >= u8.length) resolve(h.hex()); else tick().then(next);
        } catch (e) { reject(e); }
      })();
    });
  }

  // SHA-1 fallback for local HTTP contexts without WebCrypto.
  function sha1(b) {
    const size = Math.ceil((b.length + 9) / 64) * 64, block = new Uint8Array(64), w = new Int32Array(80);
    let h = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0xc3d2e1f0];
    const rot = (v, n) => (v << n) | (v >>> (32 - n));
    for (let o = 0; o < size; o += 64) {
      block.fill(0); block.set(b.subarray(o, Math.min(o + 64, b.length)));
      if (o <= b.length && b.length < o + 64) block[b.length - o] = 128;
      if (o === size - 64) { put(block, 56, Math.floor(b.length / 0x20000000)); put(block, 60, b.length * 8); }
      for (let i = 0; i < 16; i++) w[i] = u32(block, i * 4);
      for (let i = 16; i < 80; i++) w[i] = rot(w[i-3] ^ w[i-8] ^ w[i-14] ^ w[i-16], 1);
      let [a, c, d, e, f] = h;
      for (let i = 0; i < 80; i++) {
        const q = i < 20 ? ((c & d) | (~c & e)) : i < 40 ? c ^ d ^ e : i < 60 ? ((c & d) | (c & e) | (d & e)) : c ^ d ^ e;
        const k = i < 20 ? 0x5a827999 : i < 40 ? 0x6ed9eba1 : i < 60 ? 0x8f1bbcdc : 0xca62c1d6;
        const t = (rot(a, 5) + q + f + k + w[i]) | 0; f = e; e = d; d = rot(c, 30); c = a; a = t;
      }
      h = h.map((v, i) => (v + [a,c,d,e,f][i]) | 0);
    }
    return h.map(v => (v >>> 0).toString(16).padStart(8, '0')).join('');
  }
  async function digest(b, algo) {
    if (algo === 'crc32') return crc32(b).toString(16).padStart(8, '0');
    need(algo === 'sha1' || algo === 'sha256', '不支持的 FIT hash 算法：' + algo);
    if (algo === 'sha256') return sha256(b);
    if (subtle()) return toHex(await subtle().digest('SHA-1', b));
    return sha1(b);
  }

  // FDT v17 structure parser. Bounds apply to each block, token and C string.
  function fdt(b) {
    need(u32(b) === 0xd00dfeed, '不是 FIT / FDT');
    const total = u32(b, 4), so = u32(b, 8), no = u32(b, 12), ro = u32(b, 16), ver = u32(b, 20);
    need(total >= 40 && total <= b.length && ver >= 17 && u32(b, 24) <= 17, 'FIT 头版本或总长度无效');
    const s = range(range(b, 0, total), so, u32(b, 36)), names = range(range(b, 0, total), no, u32(b, 32));
    need(so >= 40 && no >= 40 && ro >= 40 && ro % 8 === 0 && so % 4 === 0 &&
      (so + s.length <= no || no + names.length <= so), 'FIT 数据块重叠或未对齐');
    let r = ro, reserves = 0;
    do { range(b, r, 16); need(r + 16 <= total && ++reserves <= 1024, 'FIT 保留内存表无效');
      if (all(b.subarray(r, r + 16), 0)) break; r += 16;
    } while (true);
    need((r + 16 <= so || ro >= so + s.length) && (r + 16 <= no || ro >= no + names.length), 'FIT 保留内存表重叠');
    let p = 0, root = null, stack = [], nodes = 0, props = 0, ended = false;
    function zterm(v, o) {
      need(o < v.length, 'FIT 字符串越界'); const e = v.indexOf(0, o);
      need(e >= o && e - o <= 4096, 'FIT 字符串未终止或过长'); return [str(v.subarray(o, e)), e + 1];
    }
    while (p < s.length) {
      const token = u32(s, p); p += 4;
      if (token === 1) {
        const [name, end] = zterm(s, p); p = Math.ceil(end / 4) * 4;
        need(++nodes <= 8192 && stack.length < 64, 'FIT 节点或深度超过上限');
        const n = {name, props: Object.create(null), children: []};
        if (stack.length) { const parent = stack[stack.length-1]; need(!parent.children.some(x => x.name === name), 'FIT 重复节点'); parent.children.push(n); }
        else { need(root === null && name === '', 'FIT 根节点无效'); root = n; }
        stack.push(n);
      } else if (token === 2) { need(stack.length, 'FIT 节点未配对'); stack.pop(); }
      else if (token === 3) {
        need(stack.length && ++props <= 32768, 'FIT 属性过多或不在节点内');
        const len = u32(s, p), off = u32(s, p+4); p += 8;
        const [name] = zterm(names, off), n = stack[stack.length-1];
        need(!Object.hasOwn(n.props, name), 'FIT 重复属性'); n.props[name] = range(s, p, len); p = Math.ceil((p + len) / 4) * 4;
      } else if (token === 4) { /* NOP */ }
      else if (token === 9) { need(root && !stack.length, 'FIT 未关闭的节点'); ended = true; break; }
      else fail('FIT token 无效');
      need(p <= s.length, 'FIT token 越界');
    }
    need(ended, 'FIT 缺少结束标记'); return {root, total};
  }
  const child = (n, name) => n.children.find(c => c.name === name);
  const propstr = (n, name) => n.props[name] ? cstr(n.props[name]) : '';
  function cell(p) { need(p && (p.length === 4 || p.length === 8), 'FIT 外置 data 单元无效'); return p.length === 4 ? u32(p) : u64(p, 0); }
  function fitData(b, tree, n) {
    const p = n.props, inline = p.data;
    if (inline) { need(!p['data-offset'] && !p['data-position'] && !p['data-size'], 'FIT data 存储方式冲突'); return inline; }
    if (!p['data-size']) { need(!p['data-offset'] && !p['data-position'], 'FIT 外置 data 缺少大小'); return null; }
    need(!!p['data-offset'] !== !!p['data-position'], 'FIT 外置 data 地址无效');
    const o = p['data-position'] ? cell(p['data-position']) : Math.ceil(tree.total / 4) * 4 + cell(p['data-offset']);
    need(o >= tree.total, 'FIT 外置 data 与头部重叠'); return range(b, o, cell(p['data-size']));
  }
  async function checkHashes(n, data, ctx) {
    if(n.children.some(c=>/^signature(?:[-@].*)?$/.test(c.name))) ctx.warnings.push('FIT 签名未验证；这里只校验段内的 hash。');
    const hashes = n.children.filter(c => /^hash(?:[-@].*)?$/.test(c.name));
    need(hashes.length <= 8, 'FIT hash 节点过多');
    for (const h of hashes) {
      const algo = propstr(h, 'algo'), value = h.props.value;
      ctx.work += data.length; need(ctx.work <= ctx.limit, '重复 hash 数据量超过上限');
      need(value && hex(value) === await digest(data, algo), 'FIT hash 不符：' + n.name + ' / ' + algo);
      ctx.hashes.push(n.name + ': ' + algo);
    }
    return hashes.length;
  }

  // Port of fw_validate_ubi() in firmware_rt3000_b.c. Deliberately rejects
  // unsupported geometries and fastmap even on boards with a looser writer.
  function validateUBI(b) {
    need(b.length >= PEB && b.length % PEB === 0 && b.length <= MAX_UBI, 'UBI 大小必须是 128 KiB 的整数倍，且不超过救援端上传上限 80 MiB');
    const tables = [], blocks = [], volumes = [], byId = new Map(); let seq;
    for (let o = 0; o < b.length; o += PEB) {
      const ec = range(b, o, 64), vid = range(b, o+PAGE, 64);
      need(magic(ec, 'UBI#') && ec[4] === 1 && u32(ec,16) === PAGE && u32(ec,20) === DATA, 'UBI EC 头或 NAND 几何不符（需 PEB 128 KiB / VID 2048 / data 4096）'); crcOK(ec,60);
      if (seq === undefined) seq = u32(ec,24); else need(seq === u32(ec,24), 'UBI image_seq 不一致');
      if (all(vid,255)) continue;
      need(magic(vid,'UBI!') && vid[4] === 1, 'UBI VID 头无效'); crcOK(vid,60);
      const id = u32(vid,8), lnum = u32(vid,12), size = u32(vid,20), pad = u32(vid,28);
      need(pad <= LEB && size <= LEB-pad, 'UBI VID 数据长度无效');
      const data = range(b,o+DATA,LEB);
      if (id === LAYOUT) {
        need(lnum < 2 && !tables[lnum] && pad === 0 && vid[5] === 1 && vid[7] === 5, 'UBI layout 卷无效'); tables[lnum] = data.subarray(0,128*172);
      } else {
        need(id < 128 && lnum < MAX_PEBS, 'UBI 卷 ID 或 LEB 超限（不接受 fastmap）'); blocks.push({id,lnum,size,pad,vid,data});
      }
    }
    need(tables[0] && tables[1] && equal(tables[0],tables[1]), 'UBI 两份卷表缺失或不一致');
    let reserved = 0, auto = 0;
    for (let id = 0; id < 128; id++) {
      const r = tables[0].subarray(id*172,(id+1)*172), count = u32(r), align = u32(r,4), pad = u32(r,8), len = u16(r,14); crcOK(r,168);
      if (!count) { need(all(r.subarray(0,168),0), 'UBI 空卷记录非零'); continue; }
      need(align > 0 && align <= LEB && len > 0 && len <= 127 && r[16+len] === 0 && (r[12] === 1 || r[12] === 2) && r[13] <= 1 && pad === LEB % align, 'UBI 卷表几何或名称无效');
      need((r[144] & ~1) === 0 && !(r[144] & 1 && auto++), 'UBI 卷标志无效或多个自动扩展卷');
      const name = cstr(r,16,len);
      need(!volumes.some(v => v.name === name), 'UBI 卷重名'); reserved += count; need(reserved <= MAX_PEBS, 'UBI 预留 PEB 超限');
      const v = {id,name,type:r[12] === 1 ? 'dynamic' : 'static',reserved:count,bytes:count*(LEB-pad),flags:r[144],pad,blocks:new Map()};
      volumes.push(v); byId.set(id,v);
    }
    const kernel = volumes.find(v=>v.name==='kernel'), root = volumes.find(v=>v.name==='ubi_rootfs') || volumes.find(v=>v.name==='rootfs');
    need(kernel && root, 'UBI 必须同时包含 kernel 和 rootfs / ubi_rootfs 卷');
    for (const x of blocks) {
      const v = byId.get(x.id), vid = x.vid, used = u32(vid,24), crc = u32(vid,32);
      need(v && x.lnum < v.reserved && x.pad === v.pad && vid[5] === (v.type==='dynamic'?1:2) && !v.blocks.has(x.lnum), 'UBI 卷块未定义、重复或超出预留范围');
      if (v.type==='dynamic' && !vid[6]) need(!x.size && !used && !crc, 'UBI dynamic VID 字段无效');
      if (v.type==='static') {
        need(!vid[6] && used > 0 && used <= v.reserved && x.lnum < used && x.size > 0, 'UBI static VID 字段无效');
        need(v.used === undefined || v.used === used, 'UBI static used_ebs 不一致'); v.used = used;
      }
      if (x.size && (vid[6] || v.type==='static')) need(crc32(x.data.subarray(0,x.size),true) === crc, 'UBI 卷数据 CRC 不符');
      v.blocks.set(x.lnum,x.data);
    }
    for (const v of volumes) for (let n=0;n<(v.used||0);n++) need(v.blocks.has(n), 'UBI static 卷缺块');
    const kd=kernel.blocks.get(0), rd=root.blocks.get(0);
    need(kd && u32(kd)===0xd00dfeed && rd && magic(rd,'hsqs'), 'UBI 内核 FIT 或根文件系统 SquashFS 魔数无效');
    const fitSize=u32(kd,4), squashSize=u64(rd,40,true), standard = u16(rd,28,true)===4 && squashSize>=96 && squashSize<=root.reserved*LEB;
    need(fitSize>=40 && fitSize<=kernel.reserved*LEB, 'UBI 内核 FIT 长度无效');
    const rootNeeded=standard?Math.ceil(squashSize/LEB):Math.max(...root.blocks.keys())+1;
    for (const [v,n] of [[kernel,Math.ceil(fitSize/LEB)],[root,rootNeeded]]) for (let i=0;i<n;i++) need(v.blocks.has(i), 'UBI 内核或根文件系统缺少连续 LEB');
    return {pebSize:PEB,lebSize:LEB,pageSize:PAGE,vidOffset:PAGE,dataOffset:DATA,imagePEBs:b.length/PEB,reservedPEBs:reserved,imageSequence:seq,standardSquashFS:standard,volumes,kernel,root,fitSize};
  }
  function volumeBytes(v, size) {
    need(size <= MAX_PEBS*LEB, '卷长度超限'); const b = new Uint8Array(size); b.fill(255);
    for (const [n,d] of v.blocks) if (n*LEB < size) b.set(d.subarray(0,Math.min(LEB,size-n*LEB)),n*LEB); return b;
  }
  function identity(info) {
    const result = {descriptions:[],configs:[],compatible:[],squashfs:info.standardSquashFS?'标准 SquashFS v4':'无法识别（可能是厂商修改的 SquashFS）'};
    try {
      const b = volumeBytes(info.kernel, info.fitSize), t = fdt(b), images = child(t.root,'images'), configs = child(t.root,'configurations');
      if (propstr(t.root,'description')) result.descriptions.push(propstr(t.root,'description'));
      if (configs) result.configs = configs.children.map(c=>c.name);
      for (const n of images ? images.children : []) {
        const desc=propstr(n,'description'); if (desc && /Linux[- ]\d/.test(desc)) result.descriptions.push(desc);
        if (propstr(n,'type')==='flat_dt' && (!n.props.compression || propstr(n,'compression')==='none')) {
          const d = fitData(b,t,n); if (!d) continue; const dt=fdt(d), comp=dt.root.props.compatible;
          if (comp) result.compatible.push(...str(comp).split('\0').filter(Boolean));
        }
      }
    } catch (_) { result.note='内核身份无法完整识别；UBI 结构校验已通过'; }
    result.descriptions=[...new Set(result.descriptions)];result.compatible=[...new Set(result.compatible)];
    return result;
  }

  // Fixed ubinize profile, matching mtd-utils libubigen: -p 128KiB -m 2048
  // -s 2048 -O 2048 -e 0 -Q 0. Only kernel/rootfs and autoresize rootfs_data.
  function ubinize(kernel, rootfs) {
    need(kernel.length>=40 && u32(kernel)===0xd00dfeed && rootfs.length>=96 && magic(rootfs,'hsqs'), 'sysupgrade 的 kernel / root 必须是 FIT / SquashFS');
    need(u16(rootfs,28,true)===4 && u64(rootfs,40,true)>=96 && u64(rootfs,40,true)<=rootfs.length, '只可为标准 SquashFS v4 的 sysupgrade 生成 UBI');
    const k=Math.ceil(kernel.length/LEB), r=Math.ceil(rootfs.length/LEB), count=k+r+2;
    need(count+3<=MAX_PEBS && count*PEB<=MAX_UBI, 'sysupgrade 生成的 UBI 过大');
    const out=new Uint8Array(count*PEB);out.fill(255);const table=new Uint8Array(128*172);
    for (let i=0;i<128;i++) {
      const rec=table.subarray(i*172,(i+1)*172);
      if(i<3) {put(rec,0,[k,r,1][i]);put(rec,4,1);rec[12]=1;const name=['kernel','rootfs','rootfs_data'][i];view(rec).setUint16(14,name.length);rec.set(new TextEncoder().encode(name),16);if(i===2) rec[144]=1;}
      put(rec,168,crc32(rec.subarray(0,168),true));
    }
    function block(pos,id,lnum,data,compat=0) {
      const base=pos*PEB,ec=out.subarray(base,base+64),vid=out.subarray(base+PAGE,base+PAGE+64);ec.fill(0);vid.fill(0);
      put(ec,0,0x55424923);ec[4]=1;put(ec,16,PAGE);put(ec,20,DATA);put(ec,60,crc32(ec.subarray(0,60),true));
      put(vid,0,0x55424921);vid[4]=1;vid[5]=1;vid[7]=compat;put(vid,8,id);put(vid,12,lnum);put(vid,60,crc32(vid.subarray(0,60),true));out.set(data,base+DATA);
    }
    block(0,LAYOUT,0,table,5);block(1,LAYOUT,1,table,5);
    let pos=2; for (const [id,b] of [[0,kernel],[1,rootfs]]) for(let o=0;o<b.length;o+=LEB) block(pos++,id,o/LEB,b.subarray(o,o+LEB));
    return out;
  }

  function tar(b) {
    const entries=new Map();let o=0,ended=false,board='';
    while(o+512<=b.length) {
      const h=range(b,o,512); if(all(h,0)) {need(all(range(b,o+512,512),0),'tar 缺少双零结束块');ended=true;break;}
      need(entries.size<4096,'tar 条目过多');
      const oct=(v)=>{const s=cstr(v).trim();need(/^[0-7]+$/.test(s),'tar 八进制字段无效');const n=parseInt(s,8);need(Number.isSafeInteger(n),'tar 大小超限');return n;};
      const checksum=oct(h.subarray(148,156));let sum=0;for(let i=0;i<512;i++)sum+=i>=148&&i<156?32:h[i];need(sum===checksum,'tar 头校验和不符');
      const prefix=cstr(h,345,155),name=(prefix?prefix+'/':'')+cstr(h,0,100),size=oct(h.subarray(124,136));
      need(!name.startsWith('/') && !name.split('/').some(x=>x==='..') && !entries.has(name),'tar 路径无效或重复');
      need(h[156]===0 || h[156]===48 || h[156]===53,'tar 只接受普通文件和目录');
      const data=range(b,o+512,size); entries.set(name,data);const m=/^sysupgrade-([^/]+)\/(CONTROL|kernel|root)$/.exec(name);
      if(m) {need(!board||board===m[1],'tar 包含多个 sysupgrade 目录');board=m[1];}
      o+=512+Math.ceil(size/512)*512;
    }
    need(ended && board,'不是完整的 OpenWrt sysupgrade tar');
    need(all(b.subarray(o+1024),0),'tar 结束块后有无法识别的数据');
    const get=n=>entries.get('sysupgrade-'+board+'/'+n);need(get('CONTROL')&&get('root'),'sysupgrade 缺少 CONTROL 或 root');
    return {board,root:get('root'),kernel:get('kernel')};
  }
  function hdr1(b,ctx) {
    range(b,0,56);const sign=u32(b,4,true);need(sign>=56&&sign<=b.length&&u16(b,12,true)===0,'HDR1 类型或签名偏移无效');
    need(crc32(b.subarray(12),true)===u32(b,8,true),'HDR1 整包 CRC 不符');
    let prev=56;const candidates=[];
    for(let i=0;i<10;i++) {
      const o=u32(b,16+i*4,true);if(!o)continue;
      need(o>=prev&&o+48<=sign,'HDR1 段重叠或越界');const h=range(b,o,48),n=u32(h,8,true),name=cstr(h,16,32);
      need(u16(h,0,true)===0xbabe&&n<=sign-o-48,'HDR1 段魔数或大小无效');prev=o+48+n;
      if(/^(root\.ubi|rootfs|firmware|ubi(?:\.img)?)$/.test(name)) candidates.push({name,data:range(b,o+48,n)});
    }
    ctx.warnings.push('HDR1 已检查 CRC；未验证厂商 RSA 签名。');
    need(candidates.length===1,'HDR1 没有唯一的系统段（root.ubi / rootfs / firmware）');return candidates[0];
  }
  // OpenWrt fwtool trailers: CRC covers every byte before the 16-byte trailer.
  // At most one metadata and one signature trailer are normally present.
  function stripFwtool(b,ctx) {
    let n=0;
    while(b.length>=16 && magic(b.subarray(b.length-16),'FWx0')) {
      need(++n<=4,'fwtool 尾部层数过多');
      const t=b.subarray(b.length-16),size=u32(t,12),type=t[8];
      need(size>=16 && size<=32768 && size<=b.length && type<=1 && all(t.subarray(9,12),0),'fwtool 尾部长度或类型无效');
      ctx.work+=b.length;need(ctx.work<=ctx.limit,'重复校验数据量超过上限');
      need(crc32(b.subarray(0,b.length-16),true)===u32(t,4),'fwtool 尾部 CRC 不符');
      if(type===1) need(size>=24 && u32(b,b.length-size)===0,'fwtool 元数据版本无效');
      if(type===0) ctx.warnings.push('fwtool 签名尾部已检查 CRC；未验证发布者签名。');
      ctx.hashes.push('fwtool: crc32');b=b.subarray(0,b.length-size);
    }
    return b;
  }
  // Rules identify containers at offset zero only. No arbitrary magic carving.
  const rules = [
    {id:'elecom',label:'ELECOM 产品头 (56)',test:b=>magic(b,'ELECOM\0\0')},
    {id:'cmoc',label:'CMOC (MSTC) 头',test:b=>magic(b,'CMOC')},
    {id:'asus-emmc',label:'ASUS eMMC uImage',test:b=>b.length>=68&&u32(b)===0x27051956&&magic(b.subarray(64),'imag')},
    {id:'h3c',label:'H3C 头 (0xa0)',test:b=>magic(b,'H3C_'),offset:160},
    {id:'ruijie',label:'锐捷头 (0x800)',test:b=>b.length>=8&&u32(b)===0x12468ace&&u32(b,4)===0xce8a4612,offset:2048},
    {id:'hdr1',label:'小米 HDR1',test:b=>magic(b,'HDR1')},
    {id:'fit',label:'FIT',test:b=>b.length>=4&&u32(b)===0xd00dfeed},
    {id:'tar',label:'OpenWrt sysupgrade tar',test:b=>b.length>=512&&(magic(b,'sysupgrade-')||magic(b.subarray(257),'ustar'))},
    {id:'ubi',label:'裸 UBI',test:b=>magic(b,'UBI#')}
  ];
  async function walk(b,ctx,chain,depth) {
    need(depth<=8&&++ctx.visits<=32,'容器嵌套深度或候选段超过上限');
    b=stripFwtool(b,ctx);
    const rule=rules.find(r=>r.test(b));
    if(!rule) {if(magic(b,'HDR2')) fail('小米 HDR2 尚未用真实样本验证，不能拆包');fail('无法识别容器，或其中没有可用的 UBI；不支持 NOR / eMMC 系统包');}
    chain=chain.concat(rule.label);
    if(rule.id==='asus-emmc') fail('ASUS eMMC 包使用独立内核 / rootfs 分区，不含本工具可输出的 UBI；该规则未用真实样本验证');
    if(rule.id==='elecom') {need(magic(range(b,56,4),'CMOC'),'ELECOM 产品头后没有 CMOC');return walk(b.subarray(56),ctx,chain,depth+1);}
    if(rule.id==='cmoc') {
      const len=u32(b,4,true),off=b.length-len;
      need(off>=140&&off<=65536&&len>=40&&u32(b,off)===0xd00dfeed,'CMOC 长度字段或 FIT 偏移无效');
      need(crc32(b.subarray(off))===u32(b,8,true),'CMOC payload CRC 不符');ctx.hashes.push('CMOC: crc32');
      return walk(b.subarray(off),ctx,chain,depth+1);
    }
    if(rule.offset) {if(rule.id==='ruijie') need(u32(b,8)===rule.offset,'锐捷头长度字段无效');need(u32(b,rule.offset)===0xd00dfeed,'厂商头后没有 FIT');return walk(b.subarray(rule.offset),ctx,chain,depth+1);}
    if(rule.id==='hdr1') {const s=hdr1(b,ctx);return walk(s.data,ctx,chain.concat(s.name),depth+1);}
    if(rule.id==='ubi') return {bytes:b,chain};
    if(rule.id==='tar') {
      const t=tar(b);ctx.board=t.board;
      if(magic(t.root,'hsqs')) {
        need(t.kernel,'sysupgrade 缺少 kernel');ctx.warnings.push('由 sysupgrade 生成 UBI：PEB 128 KiB、页 2048、LEB 126976；只适用于相同 NAND 几何与 kernel/rootfs 卷启动方式。');
        return walk(ubinize(t.kernel,t.root),ctx,chain.concat('ubinize (kernel + rootfs + rootfs_data 自动扩展)'),depth+1);
      }
      return walk(t.root,ctx,chain.concat('root'),depth+1);
    }
    const tree=fdt(b),images=child(tree.root,'images');need(images,'FIT 缺少 /images');
    const found=[],spans=[];let unhashed=0,separateRoot=false;
    for(const n of images.children) {
      const d=fitData(b,tree,n);if(!d)continue;
      if(/^rootfs([-@.].*)?$/.test(n.name)&&magic(d,'hsqs')) separateRoot=true;
      // Disallow aliasing data regions: bounds both work and ambiguous inputs.
      const start=d.byteOffset,end=start+d.length;
      need(!spans.some(s=>start<s[1]&&end>s[0]),'FIT image 数据段重叠');spans.push([start,end]);
      if(!await checkHashes(n,d,ctx)) unhashed++;
      const nested=magic(d,'UBI#')||magic(d,'HDR1')||magic(d,'H3C_')||rules.find(r=>r.id==='ruijie').test(d)||
        (/^(ubi|rootfs|root|firmware)([-@.].*)?$/.test(n.name)&&((d.length>=4&&u32(d)===0xd00dfeed)||magic(d,'sysupgrade-')));
      if(nested) found.push({name:n.name,data:d});
    }
    if(!found.length && /^Flashing emmc\b/i.test(propstr(tree.root,'description'))) fail('QSDK eMMC FIT 使用独立分区，没有 UBI（旧京东云解析路径；未用真实样本验证）');
    need(found.length===1,found.length?'FIT 有多个系统候选段，无法安全选择':separateRoot?'FIT 使用独立 SquashFS rootfs 段，没有 UBI；不能将未知启动布局合成为 UBI':'FIT 没有 UBI 系统段；可能是独立内核或 eMMC 包');
    if(unhashed) ctx.warnings.push('FIT 有 '+unhashed+' 个 image 没有 hash 节点；不能验证这些段的完整性。');
    return walk(found[0].data,ctx,chain.concat(found[0].name),depth+1);
  }
  function targetWarnings(result,target) {
    const w=[];if(!target) {w.push('尚未选择目标机型；未检查系统槽容量和机型。');return w;}
    const slots=target.slots||[];
    if(!slots.length) w.push('该机型系统槽大小不确定，请在救援页核对分区容量。');
    else {
      const fit=slots.filter(s=>result.size<=s.bytes && Math.max(result.imagePEBs,result.reservedPEBs+4)<=s.bytes/PEB);
      if(!fit.length) w.push('镜像或卷预留空间超出所选机型的系统槽；救援页会拒绝容量不足的目标。');
      else if(fit.length<slots.length) w.push('镜像只放得进这些布局：'+fit.map(s=>s.name).join('、')+'。请先在救援页核对当前布局。');
    }
    if(target.id?.startsWith('h3c-')&&result.volumes.some(v=>v.name==='wifi_fw'||v.name==='bt_fw')) w.push('此镜像含原厂 wifi_fw / bt_fw 卷。H3C 救援页只允许把它刷入原厂双系统布局；单系统布局会拒绝，请先恢复双系统分区表。');
    const id=result.identity;
    if(target.configs?.length && id.configs.length && !id.configs.some(c=>target.configs.includes(c))) w.push('内核 FIT config 与目标机型明显不符。刷错可能无法启动；可回救援页重新刷入正确 UBI。');
    const vendorComp=id.compatible.filter(c=>!/^qcom,/.test(c));
    if(target.compatible?.length&&vendorComp.length&&!vendorComp.some(c=>target.compatible.includes(c))) w.push('内核 DTB compatible 与目标机型不符。刷错可能无法启动；可回救援页重刷。');
    return w;
  }
  async function unpack(input,options={}) {
    const b=input instanceof Uint8Array?input:new Uint8Array(input);need(b.length&&b.length<=MAX_INPUT,'请选择非空且不超过 256 MiB 的固件');
    const ctx={warnings:[],hashes:[],visits:0,work:0,limit:b.length*12},picked=await walk(b,ctx,[],0),info=validateUBI(picked.bytes);
    const result={bytes:picked.bytes,size:picked.bytes.length,chain:picked.chain,sha256:await digest(picked.bytes,'sha256'),
      ...Object.fromEntries(Object.entries(info).filter(([k])=>!['volumes','kernel','root','fitSize'].includes(k))),
      volumes:info.volumes.map(v=>({id:v.id,name:v.name,type:v.type,bytes:v.bytes,reserved:v.reserved,flags:v.flags,writtenLEBs:v.blocks.size})),
      identity:identity(info),warnings:ctx.warnings,hashes:ctx.hashes,board:ctx.board||''};
    result.warnings.push(...targetWarnings(result,options.target));
    result.warnings.push('结构通过不代表机型适配。实际可写容量还取决于坏块和救援页当前布局；请以救援页校验结果为准。');
    return result;
  }
  return {unpack,validateUBI,ubinize,fdt,volumeBytes,targetWarnings,digest,crc32,sha1,sha256,rules:rules.map(({id,label})=>({id,label})),MAX_INPUT};
}
if (typeof module === 'object' && module.exports) module.exports = FWUnpackFactory();
else globalThis.FWUnpack = FWUnpackFactory();
