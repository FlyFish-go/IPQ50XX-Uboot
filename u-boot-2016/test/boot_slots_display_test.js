#!/usr/bin/env node
/* Focused host test for partition-name/capacity display and unchanged boot commands. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const mainPath = path.join(__dirname, '..', 'failsafe', 'fsdata', 'main.js');
const source = fs.readFileSync(mainPath, 'utf8');
const begin = source.indexOf('function bootSlotFirmwareText');
const end = source.indexOf('// Physical button status on RT3000-B', begin);
assert(begin >= 0 && end > begin, 'boot-slot display block not found');
const displayCode = source.slice(begin, end) +
    '\n;globalThis.testBootSlots = bootSlotsManager; globalThis.testFirmwareText = bootSlotFirmwareText;';

class Element {
    constructor(tag) {
        this.tagName = tag;
        this.children = [];
        this.className = '';
        this.hidden = false;
        this.disabled = false;
        this.checked = false;
        this.style = {};
        this.handlers = {};
        this.type = '';
        this._text = '';
        this.onclick = null;
        this.innerHTMLWrites = 0;
    }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
    set innerHTML(value) { this.innerHTMLWrites++; this._text = String(value); this.children = []; }
    appendChild(child) { this.children.push(child); return child; }
    querySelector(selector) { return selector === '.card-main-inner' ? this.inner : null; }
    setAttribute(k, v) { this[k] = v; }
    addEventListener(k, fn) { this.handlers[k] = fn; }
    findAll(tag) { return (this.tagName === tag ? [this] : []).concat(...this.children.map(c => c.findAll(tag))); }
}
class FormDataMock {
    constructor() { this.values = {}; }
    append(key, value) { this.values[key] = value; }
}

async function render(slots, language, extra = {}) {
    const section = new Element('section');
    const inner = new Element('div');
    section.inner = inner;
    section.appendChild(inner);
    const commands = [];
    const context = {
        APP_STATE: { lang: language },
        document: {
            body: { classList: { contains: () => false } },
            getElementById: id => id === 'boot_slots' ? section : null,
            createElement: tag => new Element(tag)
        },
        fetch: async (url, options) => {
            if (url === '/boot/slots') {
                return { status: 200, ok: true, json: async () => ({ slots, ...extra }) };
            }
            if (url === '/boot/default') { return { status: 200, ok: true, json: async () => ({ status: 'ok', default: 'rootfs', can_change: true, locked: false }) }; }
            if (url === '/webterm/exec') {
                const cmd = options.body.values.cmd;
                commands.push(cmd);
                return { ok: true, text: async () => 'accepted' };
            }
            throw new Error('unexpected URL ' + url);
        },
        FormData: FormDataMock
    };
    vm.createContext(context);
    vm.runInContext(displayCode, context);
    await context.testBootSlots.init();
    return { section, inner, commands, context };
}

function findLine(root, prefix) {
    const matches = root.findAll('div').map(node => node.textContent).filter(text => text.startsWith(prefix));
    return matches;
}

(async () => {
    const dual = await render([
        { name: 'rootfs', display_index: 16, physical_index: 1, offset: '0x900000', mtd: 'mtd16', size: '0x2800000', known: true, type: 'OpenWrt', label: 'OpenWrt Chaos Calmer 15.05.1', version: 'OpenWrt Chaos Calmer 15.05.1',
          kernel: '4.4.60', firmware_version: null, boot_command: 'bootipq mtd99' },
        { name: 'rootfs_1', display_index: 17, physical_index: 2, offset: '0x3100000', mtd: 'mtd17', size: 41943040, known: true, type: 'OpenWrt', label: 'OpenWrt 24.10.0', version: 'OpenWrt 24.10.0',
          kernel: '6.6.73', firmware_version: null, boot_command: 'bootipq mtd88' },
        { name: 'untrusted-rootfs', display_index: 18, mtd: 'mtd15', size: '0x2800000', known: true, type: 'OpenWrt', label: 'MUST NOT DISPLAY', version: 'MUST NOT DISPLAY' }
    ], 'zh-cn');
    const text = dual.inner.textContent;
    const nameCells = dual.inner.findAll('td').filter(cell => cell.className === 'td left');
    assert.strictEqual(nameCells[0]._text, 'rootfs');
    assert.strictEqual(nameCells[1]._text, 'rootfs_1');
    assert(nameCells[1].children[0].textContent.startsWith('物理第 2 区 · 地址范围：0x3100000 – 0x58fffff'));
    assert(nameCells[1].children[1].textContent.startsWith('\u5bb9\u91cf\uff1a'));
    assert(!text.includes('mtd'));
    assert(text.includes('\u5bb9\u91cf\uff1a41,943,040 \u5b57\u8282'));
    assert(!text.includes('MUST NOT DISPLAY'));
    assert(!text.includes('untrusted-rootfs'));
    assert(text.includes('系统：OpenWrt Chaos Calmer 15.05.1 · Linux 4.4.60'));
    assert(text.includes('系统：OpenWrt 24.10.0 · Linux 6.6.73'));
    assert(!text.includes('\u539f\u56fa\u4ef6'));
    assert.strictEqual(dual.inner.findAll('div').reduce((n, el) => n + el.innerHTMLWrites, 0), 0,
        'version strings must be inserted with textContent, never innerHTML');
    const buttons = dual.inner.findAll('button').filter(button => button.textContent.startsWith('启动 '));
    assert.strictEqual(buttons.length, 2);
    await buttons[0].onclick();
    await buttons[1].onclick();
    assert.deepStrictEqual(dual.commands, ['bootipq rootfs', 'bootipq rootfs_1']);

    assert(text.includes('物理第 1 区 · 地址范围：0x900000 – 0x30fffff'));
    assert(text.includes('物理第 2 区 · 地址范围：0x3100000 – 0x58fffff'));

    const notRead = await render([
        { name: 'rootfs', display_index: 16, mtd: 'mtd16', size: '0x2800000', known: false, type: 'unknown', label: 'Unknown system',
          version: 'unknown', kernel: '4.4.60' },
        { name: 'rootfs_1', display_index: 17, mtd: 'mtd17', size: 41943040, known: false, type: 'unknown', label: 'Unknown system',
          version: 'unknown', kernel: '', error: 'no_ubi' }
    ], 'zh-cn');
    assert(notRead.inner.textContent.includes('系统：未识别 · Linux 4.4.60'));
    assert(notRead.inner.textContent.includes('系统：未识别'));
    assert(!notRead.inner.textContent.includes('unknown ·'));

    const qsdk = await render([
        { name: 'rootfs', display_index: 16, mtd: 'mtd16', size: '0x2800000', known: true, type: 'Other', label: 'QSDK 11.5 r14',
          version: 'QSDK 11.5 r14', kernel: '4.4.60' },
        { name: 'rootfs_1', display_index: 17, mtd: 'mtd17', size: 41943040, known: true, type: 'OpenWrt', label: 'OpenWrt 21.02.7 r16847-f8282da11e', detection: 'rootfs_release_file', version: 'OpenWrt 21.02.7 r16847-f8282da11e' }
    ], 'en');
    assert(qsdk.inner.textContent.includes('rootfs'));
    assert(qsdk.inner.textContent.includes('rootfs_1'));
    assert(!qsdk.inner.textContent.includes('mtd'));
    assert(qsdk.inner.textContent.includes('Capacity: 41,943,040 bytes'));
    assert(qsdk.inner.textContent.includes('System: QSDK 11.5 r14 · Linux 4.4.60'));
    assert(qsdk.inner.textContent.includes('System: OpenWrt 21.02.7 r16847-f8282da11e'));
    assert(!qsdk.inner.textContent.includes('OpenWrt 21.02.7 r16847-f8282da11e ·'));
    assert(!qsdk.inner.textContent.includes('Unknown system'));

    // Boards without the H3C layout code: set a default, then restart; no boot-once button.
    const generic = await render([
        { name: 'rootfs', slot: 0, physical_index: 1, offset: '0x2800000', size: '0x1e00000', known: true, type: 'OpenWrt',
          version: 'OpenWrt 24.10.0', kernel: '6.6.73', boot_command: '' },
        { name: 'rootfs_1', slot: 1, physical_index: 2, offset: '0x4600000', size: '0x1e00000', known: false, type: 'unknown',
          version: 'unknown', kernel: '', boot_command: '' }
    ], 'zh-cn', { boot_supported: false, default_supported: true, read_only: false });
    assert(generic.inner.textContent.includes('设为默认后，重启路由器即启动该系统。'));
    assert(generic.inner.textContent.includes('系统：OpenWrt 24.10.0 · Linux 6.6.73'));
    const genericBoot = generic.inner.findAll('button').filter(button => button.textContent.startsWith('启动 '));
    assert(genericBoot.length === 2 && genericBoot.every(b => b.hidden === true && b.disabled === true));
    const genericDefaults = generic.inner.findAll('input').filter(input => input.type === 'checkbox');
    assert(genericDefaults.length === 2 && genericDefaults.every(c => c.disabled !== true), 'set-as-default must stay usable');

    console.log('PASS: plain partition names, capacities, release-text + kernel identity rows, unread slots, release-file version display, safe text rendering, name-derived bootipq commands, generic boards without boot-once');
})().catch(error => { console.error(error); process.exitCode = 1; });
