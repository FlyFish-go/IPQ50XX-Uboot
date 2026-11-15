// Extract the rescue page MIBIB preset generator and write both presets.
const fs = require('fs'), path = require('path'), vm = require('vm'), crypto = require('crypto'), assert = require('assert');
const [mainJs, outDir] = [process.argv[2] || path.join(__dirname, '../failsafe/fsdata/main.js'), process.argv[3]];
const src = fs.readFileSync(mainJs, 'utf8');
const begin = src.indexOf('const RT3_MIBIB_ROWS'), end = src.indexOf('// 文件上传组件类', begin);
assert(begin >= 0 && end > begin);
const ctx = {}; vm.createContext(ctx);
vm.runInContext(src.slice(begin, end) + '\nglobalThis.build = rt3BuildMibib; globalThis.nx54 = RT3_MIBIB_ROWS_NX54;', ctx);
const dual = Buffer.from(ctx.build(false)), single = Buffer.from(ctx.build(true)), xl = Buffer.from(ctx.build('xl'));
// The OEM MIBIB is identical on all four bench boards.
assert.equal(crypto.createHash('sha256').update(dual).digest('hex'),
             '0b403b917823b51560a52a8b84cc8922e774dbd4530c47989b935dadfbe2e44a');
assert.equal(single.length, 0x80000);
assert.equal(xl.length, 0x80000);
// NX54: its own factory MIBIB (two 45.25 MiB slots, no plugin).
const nx54 = Buffer.from(ctx.build(false, ctx.nx54));
assert.equal(crypto.createHash('sha256').update(nx54).digest('hex'),
             '008d80a52106da6f05d485167067a6404baa06e7eaf2b212478cf3d6040d001f');
fs.writeFileSync(path.join(outDir, 'nx54-dual.bin'), nx54);
fs.writeFileSync(path.join(outDir, 'dual.bin'), dual);
fs.writeFileSync(path.join(outDir, 'single.bin'), single);
fs.writeFileSync(path.join(outDir, 'xl.bin'), xl);
console.log('MIBIB presets: OEM dual tables (NX30 family, NX54) byte-identical to the factory MIBIBs');
