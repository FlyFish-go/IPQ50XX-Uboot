#!/usr/bin/env python3
"""Build the IPQ50XX-Uboot install guide as static HTML.

    pip install -r site/requirements.txt
    python3 site/build.py                    # writes site/dist/
    python3 -m http.server -d site/dist 8000 # preview at http://localhost:8000/

Inputs, all under site/:

    devices/*.yaml     one file per board we build U-Boot for (fields below)
    data/others.yaml   models we list but have no build for: planned / wontdo
    data/releases.yaml published builds, keyed by artifact
    pages/**/*.md      prose pages. A line that is only {{name}} is replaced by a
                       generated block, {{n_xxx}} inside text by a count.
    static/            copied as is (style.css, site.js, logo.svg, img/)

Every page gets the same frame: top bar, the section list (SIDE) on the left,
and on the right the list of its own <h2> headings. The drawings (install
flow, flash layout, TTL wiring) are the fig_* functions below; pages place
them with {{fig_flow}}, {{fig_flash}}, {{fig_wiring}}.

Two languages. Chinese is the source and is served at the root; English is
served under /en/. English text lives in site/en/: pages/**/*.md mirrors
pages/ file for file, devices/<id>.yaml holds only the translated fields of
devices/<id>.yaml (merged over it; a list replaces the whole list), and
data/others.yaml gives the translated known/missing/reason of each model by
name. Strings in this file are written T('中文', 'English'). The English build
fails on a missing page and on any Chinese left in the visible text.

Links inside the site are written as /path (no .html, no base) in pages and in
the YAML; the build turns them into relative links and fails on any link or
#anchor that does not exist. Pages work without JavaScript: static/site.js
only adds the model filter, the copy buttons and the current-heading mark.

devices/<id>.yaml fields
    id, vendor, name           required; id = file name
    status                     verified | community | untested
    install.method             bootbridge | ttl
    install.oem_firmware       bootbridge only: the stock version BootBridge needs
    install.oem_any            bootbridge only: true = the router may run any stock version;
                               oem_firmware is only the file the bridge is built from
    install.uboot              bootbridge only: U-Boot version installed (default v0.2.0)
    artifact                   ttl only: file stem of <artifact>.mbn / <artifact>-ram.uimg;
                               an untested board's artifact ends in -untested
    aliases, soc, family, order, summary
    brief                      one line for the model tables
    ttl.voltage/pins/prompt/interrupt/fdt/port
                               facts measured on our unit; leave out what nobody measured
    notes.<step id>            extra text for one generated install step (STEP_IDS)
    warnings, differences, tested, not_tested, recovery   lists of short texts
    hardware                   list of {label, value}
    slots.mechanism/note, slot_select, rescue.how/address, shell.access
    links                      list of {text, url}
    photos                     list of {file, caption, credit}; file is under static/img/.
                               Only our own photos or freely licensed ones, with the
                               author and licence in credit.
Short texts may use `code`, **bold**, [text](url) and, in longer ones,
blank-line paragraphs and "- " lists. Install steps are not written in the
YAML: ttl_steps() / web_steps() below generate them from these fields.
"""

import argparse
import html
import json
import posixpath
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown
import yaml
from markdown.extensions.toc import slugify_unicode

SITE = Path(__file__).resolve().parent
BASE = '/IPQ50XX-Uboot/'  # only 404.html needs it: GitHub Pages serves it at any path
NAME = 'IPQ50XX-Uboot'

LINKS = {
    'repo': 'https://github.com/FlyFish-go/IPQ50XX-Uboot',
    'issues': 'https://github.com/FlyFish-go/IPQ50XX-Uboot/issues',
    'report': 'https://github.com/FlyFish-go/IPQ50XX-Uboot/issues/new?template=board-report.yml',
    'ci': 'https://github.com/FlyFish-go/IPQ50XX-Uboot/actions/workflows/build.yml?query=branch%3Amain+is%3Asuccess',
    'bootbridge': '/bootbridge/',
    'h3c_release': 'https://github.com/FlyFish-go/IPQ50XX-Uboot/releases/tag/v0.2.0',
    'sponsor': 'https://ifdian.net/a/FlyFish-go',
}
QQ = '1131957442'

LANGS = ('zh', 'en')
LANG = 'zh'             # the language being built; set by build()
BUILT = LANGS           # all languages of this build
PREFIX = {'zh': '', 'en': 'en/'}


def T(zh, en):
    """The text for the language being built."""
    return en if LANG == 'en' else zh


def src_dir(*parts):
    """Translated content: site/en/... for English, site/... for Chinese."""
    return SITE.joinpath(*(('en',) if LANG == 'en' else ()), *parts)

SIDE = [  # (group title or None, [(link, (zh text, en text))]); group title is (zh, en) or None
    (None, [('/', ('首页', 'Home')), ('/devices/', ('机型列表', 'Model list'))]),
    (('安装', 'Install'), [('/install/', ('选哪种方式', 'Which method')),
                           ('/install/bootbridge', ('BootBridge 网页安装', 'BootBridge web install')),
                           ('/install/ttl', ('TTL 串口安装', 'TTL serial install')),
                           ('/install/ram-trial', ('RAM 试跑', 'RAM trial')),
                           ('/install/shell', ('系统内安装', 'In-system install'))]),
    (('装好以后', 'After installing'), [('/use/rescue', ('进入救援页', 'Enter the rescue page')),
                                        ('/use/firmware', ('刷固件与切换系统', 'Flash firmware and switch systems')),
                                        ('/use/upgrade', ('升级 U-Boot、回原厂', 'Upgrade U-Boot and go back to stock'))]),
    (('工具', 'Tools'), [('/bootbridge/', ('BootBridge', 'BootBridge')),
                         ('/tools/fwunpack', ('离线固件拆包', 'Offline firmware unpacker'))]),
    (('帮助', 'Help'), [('/help/', ('出问题怎么办', 'Troubleshooting')),
                        ('/learn/slots', ('双系统怎么切换', 'How dual systems switch')),
                        ('/learn/glossary', ('名词解释', 'Glossary'))]),
    (('项目', 'Project'), [('/contribute/', ('参与收录', 'Contribute')), ('/about', ('关于', 'About'))]),
]

# Old URLs that must keep working.
REDIRECTS = {
    'guide/index.html': '/devices/',
    'guide/rescue.html': '/use/rescue',
    'guide/recovery.html': '/help/',
    'concepts/slots.html': '/learn/slots',
    'devices/research.html': '/devices/#planned',
}

DEVICE_STATUS = {'verified': ('已验证', 'Verified'), 'community': ('社区验证', 'Community-verified'),
                 'untested': ('未验证', 'Untested')}
OTHER_STATUS = ('planned', 'wontdo')
HW_GROUP = ('硬件组', 'Hardware group')  # hardware[].label of the row the tables repeat
MECHANISM = {
    'bootconfig': ('BOOTCONFIG 双系统', 'BOOTCONFIG dual system'),
    'xiaomi-env': ('小米环境变量双系统', 'Xiaomi environment dual system'),
    'tp-env': ('TP-Link 环境变量双系统', 'TP-Link environment dual system'),
    'linksys-env': ('Linksys 环境变量双系统', 'Linksys environment dual system'),
    'single': ('单系统', 'Single system'),
}
STEP_IDS = ('prepare', 'wire', 'network', 'interrupt', 'fdt', 'ramboot', 'rescue',
            'backup', 'flash', 'verify', 'report',
            'model', 'oem', 'bridge', 'upload', 'install', 'upgrade')
DEVICE_KEYS = {'id', 'order', 'vendor', 'name', 'aliases', 'soc', 'status', 'family', 'summary',
               'brief', 'hardware', 'tested', 'not_tested', 'differences', 'warnings', 'artifact',
               'slots', 'install', 'ttl', 'notes', 'shell', 'rescue', 'slot_select', 'recovery', 'links',
               'photos'}


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- text helpers

def esc(s):
    return html.escape(str(s), quote=True)


def norm(s):
    """Model names for the filter: no case, spaces, dashes or brackets."""
    return re.sub(r'[\s\-_./·（）()【】\[\]，,、!！]+', '', str(s).lower())


def inline(src):
    """`code`, **bold** and [text](url) in one line of YAML text; the rest is escaped."""
    if not src:
        return ''
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f'\x00{len(codes) - 1}\x00'

    s = re.sub(r'`([^`]+)`', keep, esc(src))
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', s)
    return re.sub(r'\x00(\d+)\x00', lambda m: f'<code>{codes[int(m.group(1))]}</code>', s)


def text_block(src):
    """Paragraphs and "- " lists, for the longer YAML texts and generated steps."""
    if not src:
        return ''
    out = []
    for block in re.split(r'\n\s*\n', src.strip()):
        lines = [l.strip() for l in block.split('\n')]
        if all(l.startswith('- ') for l in lines):
            out.append('<ul>' + ''.join(f'<li>{inline(l[2:])}</li>' for l in lines) + '</ul>')
        else:
            out.append(f'<p>{inline("".join(lines))}</p>')
    return '\n'.join(out)


def ul(items):
    return '<ul>\n' + '\n'.join(f'<li>{inline(i)}</li>' for i in items) + '\n</ul>'


def table(head, rows, cls='', col_cls=None):
    """rows: list of (cells, attrs); cells are HTML already. col_cls: {column index: class}."""
    c = f' class="{cls}"' if cls else ''
    col_cls = col_cls or {}
    h = ''.join(f'<th>{esc(x)}</th>' for x in head)

    def td(i, x):
        return f'<td class="{col_cls[i]}">{x}</td>' if i in col_cls else f'<td>{x}</td>'

    body = '\n'.join(f'<tr{attrs}>' + ''.join(td(i, x) for i, x in enumerate(cells)) + '</tr>'
                     for cells, attrs in rows)
    return f'<div class="tw"><table{c}>\n<thead><tr>{h}</tr></thead>\n<tbody>\n{body}\n</tbody>\n</table></div>'


def kv_table(rows):
    body = '\n'.join(f'<tr><th scope="row">{esc(k)}</th><td>{v}</td></tr>' for k, v in rows)
    return f'<div class="tw"><table class="kv">\n<tbody>\n{body}\n</tbody>\n</table></div>'


# ---------------------------------------------------------------- data

def load_yaml(path):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def overlay(base, tr, where):
    """Translated fields over the source: mappings merge, anything else replaces."""
    if not isinstance(tr, dict):
        raise BuildError(f'{where}: not a mapping')
    out = dict(base)
    for k, v in tr.items():
        if k not in base:
            raise BuildError(f'{where}: "{k}" is not in the source file')
        out[k] = overlay(base[k], v, f'{where}.{k}') if isinstance(base[k], dict) else v
    return out


def load_devices():
    devices = []
    for path in sorted((SITE / 'devices').glob('*.yaml')):
        where = f'devices/{path.name}'
        d = load_yaml(path)
        if not isinstance(d, dict):
            raise BuildError(f'{where}: empty or not a mapping')
        zh_aliases = d.get('aliases') or []
        if LANG != 'zh':
            tr = src_dir('devices', path.name)
            if not tr.exists():
                raise BuildError(f'{LANG}/devices/{path.name}: missing translation')
            d = overlay(d, load_yaml(tr) or {}, f'{LANG}/devices/{path.name}')
        for k in ('id', 'vendor', 'name', 'status', 'install'):
            if not d.get(k):
                raise BuildError(f'{where}: missing "{k}"')
        extra = set(d) - DEVICE_KEYS
        if extra:
            raise BuildError(f'{where}: unknown field(s) {", ".join(sorted(extra))}')
        if d['id'] + '.yaml' != path.name:
            raise BuildError(f'{where}: id must match the file name')
        if d['status'] not in DEVICE_STATUS:
            raise BuildError(f'{where}: status must be one of {", ".join(DEVICE_STATUS)}')
        method = d['install'].get('method')
        if method not in ('bootbridge', 'ttl'):
            raise BuildError(f'{where}: install.method must be bootbridge or ttl')
        if method == 'bootbridge' and not d['install'].get('oem_firmware'):
            raise BuildError(f'{where}: a BootBridge board needs install.oem_firmware')
        if method == 'ttl' and not d.get('artifact'):
            raise BuildError(f'{where}: a TTL board needs "artifact"')
        if (d['status'] == 'untested') != str(d.get('artifact', '')).endswith('-untested'):
            raise BuildError(f'{where}: the artifact of an untested board, and only of one, ends in -untested')
        fdt = (d.get('ttl') or {}).get('fdt')
        if fdt and not re.fullmatch(r'0x[0-9a-f]+', fdt, re.I):
            raise BuildError(f'{where}: ttl.fdt must look like 0x4a9d4004')
        bad = set(d.get('notes') or {}) - set(STEP_IDS)
        if bad:
            raise BuildError(f'{where}: notes.{", notes.".join(sorted(bad))}: no such step')
        if d.get('slots') and d['slots'].get('mechanism') not in MECHANISM:
            raise BuildError(f'{where}: slots.mechanism must be one of {", ".join(MECHANISM)}')
        d['_filter_aliases'] = zh_aliases  # the filter also finds the Chinese names
        devices.append(d)
    devices.sort(key=lambda d: (d.get('order', 999), d['id']))
    return devices


def load_others():
    raw = load_yaml(SITE / 'data' / 'others.yaml') or {}
    models = raw.get('models') or []
    if LANG != 'zh':
        where = f'{LANG}/data/others.yaml'
        tr = {m['name']: m for m in (load_yaml(src_dir('data', 'others.yaml')) or {}).get('models') or []}
        unknown = set(tr) - {m['name'] for m in models}
        if unknown:
            raise BuildError(f'{where}: not in data/others.yaml: {", ".join(sorted(unknown))}')
        models = [dict(m, **{k: v for k, v in tr.get(m['name'], {}).items() if k not in ('name', 'display')},
                       display=tr.get(m['name'], {}).get('display', m['name'])) for m in models]
        missing = [m['name'] for m in models if m['name'] not in tr]
        if missing:
            raise BuildError(f'{where}: no translation for {", ".join(missing)}')
    for m in models:
        if not m.get('name') or m.get('status') not in OTHER_STATUS:
            raise BuildError(f'data/others.yaml: bad entry {m!r}')
        if m['status'] == 'planned' and not m.get('missing'):
            raise BuildError(f'data/others.yaml: {m["name"]}: a planned model needs "missing"')
        if m['status'] == 'wontdo' and not m.get('reason'):
            raise BuildError(f'data/others.yaml: {m["name"]}: needs "reason"')
    return models


def load_releases():
    raw = load_yaml(SITE / 'data' / 'releases.yaml') or {}
    return raw.get('builds') or {}


def route_of(d):
    if d['status'] == 'untested':
        return 'trial'
    return 'web' if d['install']['method'] == 'bootbridge' else 'ttl'


def full_name(d):
    sep = '' if d['vendor'].endswith('）') else ' '
    return f'{d["vendor"]}{sep}{d["name"]}'


def anchor_of(m):
    """Row id of a model that has no page of its own, so other pages can link to it."""
    return 'm-' + norm(m['name'])


def keys_of(x):
    parts = [x['name'], x.get('vendor', '') + x['name'], x.get('family', ''), x.get('artifact', '')]
    parts += x.get('aliases') or []
    if x.get('_filter_aliases') != x.get('aliases'):
        parts += x.get('_filter_aliases') or []
    return '|'.join(norm(p) for p in parts if p)


def aliases_of(d):
    return [a for a in d.get('aliases') or [] if a != d['name']]


# ---------------------------------------------------------------- drawings

def fig_flow():
    """The TTL install in five stages; only the fourth writes flash."""
    stages = [
        ('', ('接串口', 'Connect serial'), ('进入原厂 U-Boot 的命令行', 'Reach the stock U-Boot prompt')),
        ('', ('内存里运行', 'Run from RAM'), ('TFTP 传入新 U-Boot，不写闪存', 'Load the new U-Boot by TFTP; do not write flash')),
        ('', ('备份', 'Backup'), ('在救援页下载整片闪存', 'Download the whole flash from the rescue page')),
        (' class="w"', ('写入', 'Write'), ('两份 APPSBL，写完读回核对', 'Write both APPSBL copies, then read them back')),
        ('', ('重启确认', 'Reboot and check'), ('新 U-Boot 照常启动原厂系统', 'The new U-Boot boots the stock system as usual')),
    ]
    items = ''.join(f'<li{c}><b>{esc(T(*t))}</b>{esc(T(*x))}</li>' for c, t, x in stages)
    return (f'<ol class="flow">{items}</ol>\n'
            + T('<p class="figcap">前三步不写闪存，断电就回到原样。只有第 4 步改动闪存。</p>',
                '<p class="figcap">The first three steps do not write flash; power off and the router is unchanged. Only step 4 changes flash.</p>'))


def fig_flash():
    """Which partitions an install rewrites."""
    segs = [
        ('', ('SBL1 等', 'SBL1 and earlier'), ('更前面的启动程序，不动', 'Earlier bootloader stages, unchanged')),
        (' new', ('APPSBL', 'APPSBL'), ('换成本项目的 U-Boot', 'Replaced with this project\'s U-Boot')),
        (' new', ('APPSBL_1', 'APPSBL_1'), ('备用的一份，一起换', 'The backup copy, replaced as well')),
        ('', ('ART', 'ART'), ('无线校准数据，不动', 'Wireless calibration data, unchanged')),
        (' big', ('rootfs', 'rootfs'), ('系统一，不动', 'System slot 1, unchanged')),
        (' big', ('rootfs_1', 'rootfs_1'), ('系统二，不动', 'System slot 2, unchanged')),
    ]
    items = ''.join(f'<div class="seg{c}"><b>{esc(T(*t))}</b>{esc(T(*x))}</div>' for c, t, x in segs)
    return (f'<div class="flash" role="img" aria-label="{T("闪存分区示意：只有 APPSBL 和 APPSBL_1 被替换", "Flash partitions: only APPSBL and APPSBL_1 are replaced")}">{items}</div>\n'
            + T('<p class="figcap">闪存分区示意，不按比例。各机型的分区名称、数量和顺序不一样；单系统机型没有 rootfs_1。</p>',
                '<p class="figcap">Flash partitions, not to scale. Partition names, counts and order differ by model; single-system models have no rootfs_1.</p>'))


def fig_wiring():
    """Three wires between the router pads and the USB-TTL board."""
    rows = [  # y, router pin, adapter pin, kind
        (66, 'GND', 'GND', 'gnd'),
        (104, 'TX', 'RX', 'out'),
        (142, 'RX', 'TX', 'in'),
        (180, 'VCC', 'VCC', 'no'),
    ]
    out = ['<svg class="wiring" viewBox="0 0 560 214" role="img" '
           f'aria-label="{T("接线：GND 接 GND，路由器 TX 接串口板 RX，路由器 RX 接串口板 TX，VCC 不接", "Wiring: GND to GND, router TX to adapter RX, router RX to adapter TX, VCC not connected")}">',
           '<rect class="board" x="16" y="34" width="176" height="170" rx="6"/>',
           '<rect class="board" x="368" y="34" width="176" height="170" rx="6"/>',
           f'<text class="cap" x="16" y="22">{T("路由器主板", "Router board")}</text>',
           f'<text class="cap" x="368" y="22">{T("USB 转 TTL 串口板", "USB-TTL adapter")}</text>']
    for y, a, b, kind in rows:
        out.append(f'<text class="pin" x="150" y="{y + 5}" text-anchor="end">{a}</text>')
        out.append(f'<text class="pin" x="410" y="{y + 5}">{b}</text>')
        if kind == 'no':
            out.append(f'<text class="no" x="280" y="{y + 5}" text-anchor="middle">{T("不接", "not connected")}</text>')
        elif kind == 'gnd':
            out.append(f'<path class="wire gnd" d="M176 {y}H384"/>')
        elif kind == 'out':
            out.append(f'<path class="wire" d="M176 {y}H372"/>')
            out.append(f'<path class="head" d="M384 {y}l-13 -6v12z"/>')
        else:
            out.append(f'<path class="wire" d="M188 {y}H384"/>')
            out.append(f'<path class="head" d="M176 {y}l13 -6v12z"/>')
        out.append(f'<circle class="pad" cx="170" cy="{y}" r="6"/>')
        out.append(f'<circle class="pad" cx="390" cy="{y}" r="6"/>')
    out.append('</svg>')
    return ('\n'.join(out) + '\n'
            + T('<p class="figcap">箭头是数据方向：一边的 TX（发）接另一边的 RX（收）。'
                '串口板上的 VCC、3V3、5V 都不接。</p>',
                '<p class="figcap">Arrows show data direction: TX (send) on one side goes to RX (receive) on the other. '
                'VCC, 3V3 and 5V on the adapter are not connected.</p>'))


FIGS = {'flow': fig_flow, 'flash': fig_flash, 'wiring': fig_wiring}


# ---------------------------------------------------------------- install steps

def ttl_steps(d, trial):
    a = d['artifact']
    ram, mbn = f'{a}-ram.uimg', f'{a}.mbn'
    t = d.get('ttl') or {}
    n = d.get('notes') or {}
    fdt = t.get('fdt')
    steps = []

    steps.append(dict(id='prepare', title=T('准备工具和文件', 'Prepare tools and files'), note=n.get('prepare'), body='\n'.join([
        T('- USB 转 TTL 串口板，要能用 1.8 V 电平。不少 CH340、CH343、FT232 板子有电平跳线；'
          '只有 3.3 V 的板子要再加一块电平转换。',
          '- A USB-TTL adapter that supports 1.8 V logic level. Many CH340, CH343 and FT232 boards have a level jumper; '
          'a 3.3 V-only board needs a level shifter.')
        + (T(f'本机型样机实测是 {t["voltage"]}。', f'Our unit for this model measures {t["voltage"]}.') if t.get('voltage') else ''),
        T('- 杜邦线 3 根、网线 1 根，拆机用的螺丝刀和撬片。',
          '- Three jumper wires, one network cable, and a screwdriver and pry tool for opening the case.'),
        T('- 电脑上装好串口终端（PuTTY 或 MobaXterm）和 TFTP 服务器（Windows 用 Tftpd64）。',
          '- A serial terminal (PuTTY or MobaXterm) and a TFTP server (Tftpd64 on Windows) on the computer.'),
        (T(f'- 试跑文件 `{ram}`，见上面表格里的「下载」。', f'- The trial file `{ram}`, see "Download" in the table above.') if trial else
         T(f'- 本机型的两个文件：`{ram}`（在内存里试跑，先用它）和 `{mbn}`（写进闪存的正式版），'
           '见上面表格里的「下载」。放进同一个文件夹。',
           f'- The two files for this model: `{ram}` (run from RAM, use this first) and `{mbn}` '
           '(the final image to write to flash). See "Download" in the table above. Put them in the same folder.')),
    ])))

    steps.append(dict(id='wire', title=T('拆机，接三根线', 'Open the case and connect three wires'), note=n.get('wire'), body='\n'.join([
        T('拆开外壳，在主板上找标着 GND、TX、RX（有时还有 VCC）的 4 个焊盘或排针',
          'Open the case and find the four pads or header pins marked GND, TX, RX (and sometimes VCC)')
        + (T(f'（串口在 {t["pins"]}）', f' (serial console at {t["pins"]})') if t.get('pins') else '')
        + T('。只接三根线：', '. Connect only three wires:'),
        '',
        T('- 路由器 GND 接串口板 GND', '- Router GND to adapter GND'),
        T('- 路由器 TX 接串口板 RX', '- Router TX to adapter RX'),
        T('- 路由器 RX 接串口板 TX', '- Router RX to adapter TX'),
        '',
        T('**VCC 不要接**，路由器用自己的电源。串口终端设成 115200、8N1、无流控。'
          '找焊盘的方法见 [TTL 串口安装](/install/ttl#接线)。',
          '**Do not connect VCC**; the router uses its own power. Set the serial terminal to 115200, 8N1, no flow control. '
          'See [TTL serial install](/install/ttl#wiring) to locate the pads.'),
    ]), fig='wiring', warn=T('电平接错可能烧坏主芯片的串口脚。没把握时，先用万用表量路由器 TX 对 GND 的电压：'
             '通电后在 1.8 V 左右，就必须用 1.8 V 电平。',
             'A wrong logic level can damage the main chip\'s serial pins. If unsure, measure router TX against GND with a '
             'multimeter: about 1.8 V after power on means you must use 1.8 V logic level.')))

    steps.append(dict(id='network', title=T('电脑接网线，设好地址', 'Connect the computer and set its address'), note=n.get('network'), body='\n'.join([
        T(f'网线一头接电脑，一头接路由器：{t.get("port", "LAN 口")}。把电脑的有线网卡手动设成：',
          f'Connect one end of the network cable to the computer and the other to the router: {t.get("port", "the LAN port")}. '
          'Set the computer\'s wired network adapter manually:'),
        '',
        T('- IP 地址 `192.168.1.2`', '- IP address `192.168.1.2`'),
        T('- 子网掩码 `255.255.255.0`', '- Netmask `255.255.255.0`'),
        T('- 网关、DNS 留空', '- Leave gateway and DNS empty'),
        '',
        T('打开 Tftpd64，「Current Directory」选放文件的文件夹，「Server interfaces」选 `192.168.1.2`。'
          'Windows 防火墙弹窗时点「允许」。详细设置见 [TTL 串口安装](/install/ttl#电脑设置)。',
          'Open Tftpd64. Set "Current Directory" to the folder with the files, and "Server interfaces" to '
          '`192.168.1.2`. When Windows Firewall prompts, click "Allow". For details see '
          '[TTL serial install](/install/ttl#computer-setup).'),
    ])))

    steps.append(dict(
        id='interrupt', title=T('截停原厂 U-Boot', 'Interrupt stock U-Boot'), note=n.get('interrupt'),
        body=T('串口终端打开串口板对应的 COM 口，再给路由器通电。启动信息开始滚动后，看到 '
               '`Hit any key to stop autoboot` 时',
               'Open the COM port for the adapter in the serial terminal, then power on the router. When the startup '
               'messages begin scrolling and you see `Hit any key to stop autoboot`')
             + (T(f'：{t["interrupt"]}', f': {t["interrupt"]}') if t.get('interrupt')
                else T('马上按一下回车', 'press Enter at once'))
             + T('。停在命令提示符下就对了。', '. You should stop at the command prompt.'),
        expect=f'Hit any key to stop autoboot:  0\n{t.get("prompt", "IPQ5018#")}',
        expect_note=None if t.get('prompt') else T('提示符的名字各机型不一样，停在提示符下就行。',
                                                   'The prompt name differs by model; stopping at a prompt is enough.'),
        fail='\n'.join([
            T('- **一个字都没有**：TX、RX 可能接反了，对调再试；检查 GND 接了没有、COM 口选对没有。',
              '- **No output at all**: TX and RX may be swapped; swap them and try again. Check GND is connected and the COM port is correct.'),
            T('- **全是乱码**：波特率不是 115200，或者电平不对。',
              '- **Garbled output**: the baud rate is not 115200, or the logic level is wrong.'),
            T('- **来不及按**：通电前就按住回车不放，看到提示符再松开。',
              '- **Too slow to press**: hold Enter before powering on, and release it when the prompt appears.'),
            T('- **能看不能输入**：路由器 RX 那根线没接好，或者 RX 脚被电阻拉到了地'
              '（例如 [TCL T30 Pro](/devices/tcl-t30-pro)）。',
              '- **Output but no input**: the router RX wire is not connected properly, or the RX pin is pulled to ground '
              'by a resistor (for example [TCL T30 Pro](/devices/tcl-t30-pro)).'),
        ])))

    steps.append(dict(
        id='fdt', title=T('记下设备树地址', 'Note the device tree address'), note=n.get('fdt'),
        body=T('下一步要用到原厂 U-Boot 的设备树地址。执行下面这条命令，记下等号后面的值。这一步只读，不改任何东西。',
               'The next step needs the device tree address from stock U-Boot. Run the command below and write down the '
               'value after the equals sign. This step is read-only and changes nothing.'),
        cmd='printenv fdtcontroladdr',
        expect=f'fdtcontroladdr={fdt[2:] if fdt else "4a9……"}',
        expect_note=(T('这是我们样机上的值，你的机器以屏幕上显示的为准。',
                       'This is the value on our unit; use what your router shows.') if fdt
                     else T('每种机型不一样，不要照抄别人的地址。',
                            'It differs by model; do not copy someone else\'s address.')),
        fail=T('- **提示没有这个变量**：执行 `bdinfo`，找 `fdt_blob` 那一行的地址。',
               '- **Variable not found**: run `bdinfo` and find the address on the `fdt_blob` line.')))

    steps.append(dict(
        id='ramboot', title=T('在内存里运行新 U-Boot', 'Run the new U-Boot from RAM'), note=n.get('ramboot'),
        body=T('逐行输入下面四条命令', 'Enter the four commands below one by one')
             + ('' if fdt else T('，最后一行的地址换成上一步记下的值（前面加 `0x`）',
                                 ', replacing the address on the last line with the value you noted (prefixed with `0x`)'))
             + T('。新 U-Boot 只在内存里运行，**不写闪存**，断电就回到原样。',
                 '. The new U-Boot runs only from RAM and **does not write flash**; power off and the router is unchanged.'),
        cmd='\n'.join([
            'setenv ipaddr 192.168.1.1',
            'setenv serverip 192.168.1.2',
            f'tftpboot 0x44000000 {ram}',
            f'bootm 0x44000000 - {fdt or T("<上一步的地址>", "<the address from the previous step>")}',
        ]),
        expect='\n'.join([
            'Bytes transferred = ……',
            '## Booting kernel from Legacy Image at 44000000 ...',
            'Starting kernel ...',
            '',
            'U-Boot 2016.01-……',
        ] + (['UNTESTED BOARD: not verified on hardware'] if trial else [])),
        expect_note=T('中间还有很多行，大致是这个顺序。',
                      'There are more lines in between; roughly this order.'),
        fail='\n'.join([
            T('- **一直打印 `T T T` 或 `TFTP error`**：检查电脑 IP 是不是 `192.168.1.2`，Tftpd64 有没有选对网卡和文件夹，'
              '防火墙有没有放行；网线换一个 LAN 口试试。',
              '- **Keeps printing `T T T` or `TFTP error`**: check that the computer IP is `192.168.1.2`, that Tftpd64 '
              'has the right adapter and folder, and that the firewall allows it; try another LAN port.'),
            T('- **`Wrong Image Format`**：文件用错了，这里要用 `-ram.uimg`，不是 `.mbn`。',
              '- **`Wrong Image Format`**: wrong file. Use `-ram.uimg` here, not `.mbn`.'),
            T('- **打印 `Booting restricted without authentication!!` 然后重启**：这台机器开了安全启动，'
              '**不能安装**，到此为止。',
              '- **Prints `Booting restricted without authentication!!` and reboots**: this router has secure boot enabled. '
              '**It cannot be installed**; stop here.'),
            T('- **停在 `Starting kernel ...` 不动**：设备树地址写错了，回上一步核对。',
              '- **Stops at `Starting kernel ...`**: the device tree address is wrong; go back and check it.'),
        ])))

    steps.append(dict(
        id='rescue', title=T('打开救援页', 'Open the rescue page'), note=n.get('rescue'),
        body=T('新 U-Boot 起来后也会倒计时，再按一次回车截停，然后输入 `httpd`。浏览器打开 `http://192.168.1.1`。',
               'The new U-Boot also counts down at startup. Press Enter again to interrupt it, then enter `httpd`. '
               'Open `http://192.168.1.1` in a browser.') + INCOGNITO()
             + (T('\n\n**只看，不写**：不要点「写入」「更新」一类的按钮，也不要在串口里执行 `saveenv`、`nand write`、'
                  '`bootconfig set`。逐项记下：每个网口能不能打开救援页、「系统信息」里的闪存型号、各个 LED 和按键的表现。',
                  '\n\n**Look only, write nothing**: do not click buttons such as "Write" or "Update", and do not run '
                  '`saveenv`, `nand write` or `bootconfig set` in the serial console. Note down: whether the rescue page '
                  'opens on each network port, the flash model in "System Info", and how the LEDs and buttons behave.')
                if trial else ''),
        cmd='httpd',
        check=(T('浏览器里出现救援页。', 'The rescue page appears in the browser.') if trial
               else T(f'浏览器里出现救援页，「系统信息」里的型号是 {full_name(d)}。',
                      f'The rescue page appears in the browser, and "System Info" shows {full_name(d)}.')),
        fail='\n'.join([
            T('- **网页打不开**：确认电脑 IP 还是 `192.168.1.2`；关掉代理和 VPN；一次只接一根网线，换一个 LAN 口试试。',
              '- **The page will not open**: check that the computer IP is still `192.168.1.2`; turn off proxies and VPNs; '
              'use only one network cable at a time and try another LAN port.'),
        ] + ([] if trial else [T('- **型号不对**：马上断电，不要继续，到 Issue 反馈。',
                                 '- **Wrong model**: power off at once, do not continue, and report it in an Issue.')]))))

    if trial:
        steps.append(dict(
            id='report', title=T('提交试跑报告，然后断电', 'Submit the trial report, then power off'),
            body=T(f'不管成功还是失败，都请用[试跑报告表单]({LINKS["report"]})告诉我们：机型和铭牌上的硬件版本、启动日志、'
                   '闪存型号、每个网口能不能打开救援页、LED 和按键的表现。日志里的 MAC 和序列号先打码。'
                   '一块板要靠这样的报告才能改成「已验证」。\n\n'
                   '最后断电再通电，路由器照常启动原厂系统。整个过程没有写过闪存。',
                   f'Whether it succeeds or fails, tell us with the [trial report form]({LINKS["report"]}): the model and '
                   'hardware version on the label on the bottom of the router, the boot log, the flash model, whether the '
                   'rescue page opens on each network port, and how the LEDs and buttons behave. Redact MAC addresses and '
                   'serial numbers in the log. A board needs a report like this to become "Verified".\n\n'
                   'Finally power off and back on; the router boots the stock system as usual. No flash was written at any point.'),
            warn=T('试跑一切正常也不代表可以刷入。等维护者确认、改成「已验证」以后再说。',
                   'A clean trial does not mean it can be flashed. Wait for a maintainer to confirm and mark it "Verified".')))
        return steps

    steps.append(dict(
        id='backup', title=T('备份整片闪存', 'Back up the whole flash'), note=n.get('backup'),
        body=T('在救援页「闪存备份」里下载整片闪存，保存到电脑，再复制一份到 U 盘或网盘。'
               '以后想回原厂、或者出问题求助，都要靠这份备份。',
               'In the rescue page, use "Flash Backup" to download the whole flash. Save it on the computer and make '
               'another copy on a USB drive or in cloud storage. You will need this backup to go back to stock or to ask '
               'for help if something goes wrong.'),
        warn=T('备份里有这台机器的校准数据（ART）、MAC 和序列号。只留给自己，不要发到群里或 Issue。',
               'The backup contains this router\'s calibration data (ART), MAC addresses and serial numbers. Keep it to '
               'yourself; do not post it in groups or Issues.'),
        stop=T('没拿到完整备份之前，不要做下一步。', 'Do not continue until you have a complete backup.')))

    steps.append(dict(
        id='flash', title=T('写入 U-Boot', 'Write U-Boot'), note=n.get('flash'),
        body=T(f'打开救援页「U-Boot 更新」，选择 `{mbn}`（不是 `-ram.uimg`），确认写入。'
               '两份 APPSBL 会一起写入，写完自动读回核对。',
               f'Open "U-Boot Update" in the rescue page, select `{mbn}` (not `-ram.uimg`) and confirm the write. '
               'Both APPSBL copies are written, then read back and checked automatically.'),
        check=T('页面提示写入成功。', 'The page reports a successful write.'),
        warn=T('写入的十几秒里不要断电，也不要关网页。',
               'Do not power off or close the page during the 10 to 20 seconds of the write.'),
        fail='\n'.join([
            T('- **页面拒绝这个文件**：确认是本机型的 `.mbn`，再核对文件的 SHA-256。不要拿别的机型的文件硬刷。',
              '- **The page rejects the file**: check it is the `.mbn` for this model and verify its SHA-256. Never flash a '
              'file from another model.'),
            T('- **写到一半报错**：先别断电，截图到 QQ 群或 Issue 求助。新 U-Boot 还在内存里运行，可以重新写。',
              '- **An error mid-write**: do not power off; take a screenshot and ask for help in the QQ group or an Issue. '
              'The new U-Boot is still running from RAM, so you can write again.'),
        ])))

    r = d.get('rescue')
    steps.append(dict(
        id='verify', title=T('断电重启，确认装好', 'Power cycle and confirm the install'), note=n.get('verify'),
        body=T('断电，等几秒再通电。串口里应该出现新 U-Boot 的版本信息，然后照常进入原厂系统。',
               'Power off, wait a few seconds, then power on. The serial console should show the new U-Boot version, '
               'then boot the stock system as usual.')
             + (T(f'以后要进救援页：{r["how"]}，打开 `http://{r.get("address", "192.168.1.1")}`{INCOGNITO_SHORT()}。',
                  f'To enter the rescue page later: {r["how"]}, then open '
                  f'`http://{r.get("address", "192.168.1.1")}`{INCOGNITO_SHORT()}.') if r else ''),
        expect='U-Boot 2016.01-……',
        expect_note=T('版本号后面跟着提交号和日期，和第 6 步在内存里运行的那个一样。',
                      'The version string includes a commit hash and date, the same as the one run from RAM in step 6.'),
        fail='\n'.join([
            T('- **还是原厂 U-Boot 的信息**：写入没有生效，回到第 6 步重来。',
              '- **Still shows stock U-Boot**: the write did not take effect; go back to step 6 and repeat.'),
            T('- **新 U-Boot 起来了，系统起不来**：截停后输入 `httpd` 进救援页，见[出问题怎么办](/help/)。',
              '- **The new U-Boot starts but the system does not**: interrupt it, enter `httpd` to open the rescue page, '
              'and see [Troubleshooting](/help/).'),
        ])))
    return steps


# The rescue page has a browser-cache bug: a normal window can show a stale page.
def INCOGNITO():
    return T('建议全程用浏览器的无痕（隐私）窗口打开救援页，普通窗口可能读到缓存里的旧页面，见[进入救援页](/use/rescue)。',
             'Use a private (incognito) browser window for the rescue page throughout; a normal window may show a cached '
             'old page. See [Enter the rescue page](/use/rescue).')


def INCOGNITO_SHORT():
    return T('（建议用无痕窗口）', '(use a private window)')


def web_steps(d):
    oem = d['install']['oem_firmware']
    ub = d['install'].get('uboot', 'v0.2.0')
    n = d.get('notes') or {}
    r = d.get('rescue') or {}
    return [
        dict(id='model', title=T('确认机型', 'Confirm the model'), note=n.get('model'),
             body=T(f'看路由器底部铭牌，型号是 {d["name"]}', f'Check the label on the bottom of the router; the model is {d["name"]}')
                  + (T(f' 或 {"、".join(aliases_of(d))}', f' or {" / ".join(aliases_of(d))}') if aliases_of(d) else '')
                  + T('。全程不用拆机，只要一台有网线口的电脑和一根网线。',
                      '. You do not need to open the case; all you need is a computer with a network port and one network cable.')),
        dict(id='oem', title=T(f'下载官方固件 {oem}', f'Download official firmware {oem}'), note=n.get('oem'),
             body=T(f'BootBridge 用官方固件 `{oem}` 生成桥接包。打开 [BootBridge 网页版]({LINKS["bootbridge"]})，'
                    '选好机型，按第 2 步取得这个文件。路由器上的原厂系统不用先升级。',
                    f'BootBridge uses official firmware `{oem}` to build the bridge package. Open '
                    f'[BootBridge web app]({LINKS["bootbridge"]}), choose your model, and get this file in step 2. '
                    'You do not need to upgrade the stock system first.'),
             check=T(f'BootBridge 显示官方固件 `{oem}` 校验通过。',
                     f'BootBridge shows that official firmware `{oem}` passed validation.'))
        if d['install'].get('oem_any') else
        dict(id='oem', title=T(f'原厂系统升级到 {oem}', f'Upgrade the stock system to {oem}'), note=n.get('oem'),
             body=T(f'BootBridge 只认这一个官方版本。打开 [BootBridge 网页版]({LINKS["bootbridge"]})，选好机型，'
                    f'第 2 步会给出官方固件的下载地址。登录路由器的原厂后台，在系统升级里先升级到 `{oem}`。'
                    '已经是这个版本的可以跳过。',
                    f'BootBridge accepts only this official version. Open [BootBridge web app]({LINKS["bootbridge"]}), '
                    'choose your model, and step 2 gives the download link for the official firmware. Log in to the stock '
                    f'web admin and upgrade to `{oem}` first. Skip this if you already have that version.'),
             check=T(f'原厂后台显示的版本号是 `{oem}`。', f'The stock web admin shows version `{oem}`.')),
        dict(id='bridge', title=T('生成桥接包', 'Build the bridge package'), note=n.get('bridge'),
             body=T('回到 BootBridge，载入同一份官方固件，生成桥接包。固件只在你的浏览器里处理，不会上传。',
                    'Go back to BootBridge, load the same official firmware and build the bridge package. The firmware '
                    'is processed in your browser only and is never uploaded.'),
             fail=T(f'- **提示版本或校验不对**：下载的不是 `{oem}`，或者文件没下完整，重新下载。',
                    f'- **Version or validation error**: you did not download `{oem}`, or the file is incomplete. Download it again.')),
        dict(id='upload', title=T('在原厂后台上传桥接包', 'Upload the bridge package in the stock web admin'), note=n.get('upload'),
             body=T('在原厂后台的系统升级里上传桥接包，路由器会重启进入桥接系统。',
                    'Upload the bridge package in the stock web admin\'s upgrade page. The router reboots into the bridge system.'),
             warn=T('`appsbl.mbn` 这类 U-Boot 文件不能直接传到原厂升级页。第一次安装只能走 BootBridge。',
                    'U-Boot files such as `appsbl.mbn` cannot be uploaded to the stock upgrade page. The first install '
                    'must go through BootBridge.')),
        dict(id='install', title=T('识别、备份、安装', 'Detect, back up and install'), note=n.get('install'),
             body=T('电脑用网线接路由器的 LAN 口，网卡设为自动获取地址，浏览器打开 `http://192.168.10.1`，'
                    '确认识别结果，先生成并下载备份，校验文件后再点「安装」。\n\n'
                    '备份文件保存在自己电脑上，里面有本机的校准数据和序列号，不要发给别人。'
                    '安装成功后按页面提示重启，照常进入原厂系统。',
                    'Connect the computer to the router\'s LAN port with a network cable, set the adapter to obtain an '
                    'address automatically, and open `http://192.168.10.1` in a browser. Check the detection result, '
                    'generate and download a backup first, then click "Install" after verifying the file.\n\n'
                    'Keep the backup on your own computer; it contains this router\'s calibration data and serial number. '
                    'Do not share it. After a successful install, reboot as the page instructs; the stock system boots as usual.'),
             stop=T('备份文件没保存好之前，不要点「安装」。', 'Do not click "Install" until the backup is saved.'),
             fail='\n'.join([
                 T('- **打不开 `192.168.10.1`**：看电脑有没有拿到 `192.168.10.x` 的地址；换一个 LAN 口；等一分钟再刷新。',
                   '- **Cannot open `192.168.10.1`**: check that the computer has a `192.168.10.x` address; try another LAN '
                   'port; wait a minute and reload.'),
                 T('- **识别不通过**：不要换别的机型的文件硬装，截图到 QQ 群或 Issue。',
                   '- **Detection fails**: do not force a file from another model; take a screenshot and ask in the QQ group or an Issue.'),
             ])),
        dict(id='upgrade', title=T(f'确认 U-Boot {ub}', f'Confirm U-Boot {ub}'), note=n.get('upgrade'),
             body=((T(f'BootBridge 安装的是 U-Boot 测试版 `{ub}`。', f'BootBridge installed the U-Boot test build `{ub}`.')
                    if ub != 'v0.2.0' else
                    T('新版 BootBridge 直接安装 v0.2.0 正式版，不需要再经过旧版或 RAM 救援版升级。',
                      'The new BootBridge installs the v0.2.0 release directly; no upgrade through an older version or the '
                      'RAM rescue build is needed.'))
                   + (T('首次启动稳定后，按住 Reset 通电，红灯闪满 3 下后松手，'
                        '打开 `http://192.168.10.1` 进救援页，在「系统信息」核对版本和硬件系列。',
                        'After the first boot is stable, hold Reset while powering on and release it after the red LED '
                        'flashes three times. Open `http://192.168.10.1` to enter the rescue page and check the version '
                        'and hardware family in "System Info".') if ub == 'v0.2.0' else
                      T(f'首次启动稳定后，{r.get("how", "按住 Reset 通电")}，'
                        '打开 `http://192.168.10.1` 进救援页，在「系统信息」核对版本。',
                        f'After the first boot is stable, {r.get("how", "hold Reset while powering on")}. Open '
                        '`http://192.168.10.1` to enter the rescue page and check the version in "System Info".'))
                   + INCOGNITO()),
             check=(T('重启后，救援页「系统信息」里的 U-Boot 版本带 `v0.2.0`。',
                      'After reboot, "System Info" in the rescue page shows a U-Boot version containing `v0.2.0`.')
                    if ub == 'v0.2.0' else
                    T(f'重启后，救援页「系统信息」里有 U-Boot 版本信息（{ub} 的版本串是 `v0.2.0-1255aa29bb43`）。',
                      f'After reboot, "System Info" in the rescue page shows the U-Boot version '
                      f'(the version string for {ub} is `v0.2.0-1255aa29bb43`).'))),
        dict(id='verify', title=T('记住怎么进救援页', 'Remember how to enter the rescue page'), note=n.get('verify'),
             body=T(f'以后进救援页：{r.get("how", "按住 Reset 通电")}，打开 `http://{r.get("address", "192.168.10.1")}`{INCOGNITO_SHORT()}。',
                    f'To enter the rescue page later: {r.get("how", "hold Reset while powering on")}, then open '
                    f'`http://{r.get("address", "192.168.10.1")}`{INCOGNITO_SHORT()}.')
                  + (T(f'\n\n用按键切换系统：{d["slot_select"]}', f'\n\nSwitch systems with the button: {d["slot_select"]}')
                     if d.get('slot_select') else '')
                  + T('\n\n要刷第三方固件，见[刷固件与切换系统](/use/firmware)。',
                      '\n\nTo flash third-party firmware, see [Flash firmware and switch systems](/use/firmware).')),
    ]


def term(label, text, out=False):
    cls = 'term out' if out else 'term'
    return (f'<div class="{cls}"><div class="term-h"><span>{esc(label)}</span></div>'
            f'<pre><code>{esc(text)}</code></pre></div>')


def render_steps(steps):
    out = ['<ol class="steps">']
    for s in steps:
        out.append(f'<li><h3 id="step-{s["id"]}">{esc(s["title"])}</h3>')
        out.append(text_block(s['body']))
        if s.get('fig'):
            out.append(FIGS[s['fig']]())
        if s.get('note'):
            out.append(f'<p class="thisdev"><strong>{T("本机型：", "This model: ")}</strong>{inline(s["note"])}</p>')
        if s.get('cmd'):
            out.append(term(T('在串口里输入', 'Enter in the serial console'), s['cmd']))
        if s.get('expect'):
            out.append(term(T('应该看到', 'You should see'), s['expect'], out=True))
            if s.get('expect_note'):
                out.append(f'<p class="hint">{inline(s["expect_note"])}</p>')
        if s.get('check'):
            out.append(f'<p><span class="label">{T("应该看到：", "You should see: ")}</span>{inline(s["check"])}</p>')
        if s.get('warn'):
            out.append(f'<p class="warn"><strong>{T("注意：", "Note: ")}</strong>{inline(s["warn"])}</p>')
        if s.get('stop'):
            out.append(f'<p><strong>{inline(s["stop"])}</strong></p>')
        if s.get('fail'):
            out.append(f'<details><summary>{T("不对的话", "If something is wrong")}</summary>\n{text_block(s["fail"])}\n</details>')
        out.append('</li>')
    out.append('</ol>')
    return '\n'.join(out)


# ---------------------------------------------------------------- device pages

def download_cell(d, route, releases):
    ub = d['install'].get('uboot', 'v0.2.0')
    if route == 'web' and ub != 'v0.2.0':
        url = f'https://github.com/FlyFish-go/IPQ50XX-Uboot/releases/tag/{ub}'
        return T(f'安装不用单独下载，BootBridge 会写入 U-Boot。测试版的 <code>.mbn</code> 在 '
                 f'<a href="{esc(url)}">{esc(ub)} 发布页</a>，只给已有串口或 U-Boot 环境的人手动刷。',
                 f'No separate download is needed for installation; BootBridge writes U-Boot. The test build\'s '
                 f'<code>.mbn</code> is on the <a href="{esc(url)}">{esc(ub)} release page</a>, for manual flashing only '
                 'by people who already have a serial console or U-Boot access.')
    if route == 'web':
        return T(f'安装不用单独下载，BootBridge 会写入 U-Boot。以后升级用 '
                 f'<a href="{LINKS["h3c_release"]}">v0.2.0 发布页</a>里的 '
                 '<code>h3c-hw-x.mbn</code>，x 是救援页「系统信息」里的硬件系列；每组一个文件，闪存型号自动识别。',
                 f'No separate download is needed for installation; BootBridge writes U-Boot. For later upgrades use '
                 f'<code>h3c-hw-x.mbn</code> from the <a href="{LINKS["h3c_release"]}">v0.2.0 release page</a>, where x is '
                 'the hardware family in "System Info" on the rescue page. There is one file per group, and the flash '
                 'model is detected automatically.')
    a = d['artifact']
    files = f'<code>{esc(a)}-ram.uimg</code>' + ('' if route == 'trial' else T(f' 和 <code>{esc(a)}.mbn</code>', f' and <code>{esc(a)}.mbn</code>'))
    rel = releases.get(a)
    if rel:
        return T(f'<a href="{esc(rel["url"])}">{esc(rel["tag"])} 发布页</a>：{files}。'
                 '下载后核对 SHA-256（Windows：<code>certutil -hashfile 文件名 SHA256</code>）。',
                 f'<a href="{esc(rel["url"])}">{esc(rel["tag"])} release page</a>: {files}. '
                 'Check the SHA-256 after downloading (Windows: <code>certutil -hashfile FILENAME SHA256</code>).')
    zipname = re.sub(r'-untested$', '', a)
    return T(f'还没有正式发布。<a href="{LINKS["ci"]}">GitHub Actions</a> 最新一次成功的构建里有 '
             f'<code>{esc(zipname)}</code>（zip，下载要登录 GitHub），里面是 {files}。',
             f'No official release yet. The latest successful <a href="{LINKS["ci"]}">GitHub Actions</a> build contains '
             f'<code>{esc(zipname)}</code> (zip; sign in to GitHub to download), which includes {files}.')


def facts_of(d, route, releases):
    t = d.get('ttl') or {}
    rows = []
    if route == 'web':
        rows.append((T('安装方式', 'Install method'), inline(T('[BootBridge 网页安装](/install/bootbridge)，不用拆机',
                                                              '[BootBridge web install](/install/bootbridge), no need to open the case'))))
        if d['install'].get('oem_any'):
            rows.append((T('官方固件', 'Official firmware'),
                         T(f'<code>{esc(d["install"]["oem_firmware"])}</code>（生成桥接包用，原厂系统不用升级）',
                           f'<code>{esc(d["install"]["oem_firmware"])}</code> (used to build the bridge package; no stock upgrade needed)')))
        else:
            rows.append((T('需要的原厂版本', 'Required stock version'), f'<code>{esc(d["install"]["oem_firmware"])}</code>'))
    else:
        rows.append((T('安装方式', 'Install method'),
                     inline(T('[TTL 串口安装](/install/ttl)，要拆机', '[TTL serial install](/install/ttl), open the case')
                            if route == 'ttl' else
                            T('[RAM 试跑](/install/ram-trial)：要拆机接 TTL，不写闪存',
                              '[RAM trial](/install/ram-trial): open the case and connect TTL; no flash writes'))))
        rows.append((T('串口', 'Serial console'), esc(T('，', ', ').join(x for x in ('115200 8N1', t.get('voltage'), t.get('pins')) if x))))
        rows.append((T('截停原厂 U-Boot', 'Interrupt stock U-Boot'),
                     inline(t.get('interrupt') or T('看到 `Hit any key` 时按回车', 'Press Enter when you see `Hit any key`'))))
        rows.append((T('设备树地址', 'Device tree address'),
                     inline(T(f'`{t["fdt"]}`（样机实测）', f'`{t["fdt"]}` (measured on our unit)') if t.get('fdt')
                            else T('没人测过，以 `printenv fdtcontroladdr` 为准',
                                   'Not measured; use `printenv fdtcontroladdr` as the reference'))))
    r = d.get('rescue')
    if r:
        rows.append((T('进救援页', 'Enter the rescue page'),
                     inline(T(f'{r["how"]}，打开 `http://{r.get("address", "192.168.1.1")}`{INCOGNITO_SHORT()}',
                              f'{r["how"]}, then open `http://{r.get("address", "192.168.1.1")}`{INCOGNITO_SHORT()}'))))
    for h in d.get('hardware') or []:
        if h['label'] in HW_GROUP:
            rows.append((h['label'], inline(h['value'])))
    rows.append((T('下载', 'Download'), download_cell(d, route, releases)))
    return rows


def status_line(d, route):
    if route == 'trial':
        parts = [f'<span class="dot untested"></span><b>{T(*DEVICE_STATUS["untested"])}</b>',
                 T('只能 RAM 试跑，不写闪存', 'RAM trial only, no flash writes')]
    else:
        parts = [f'<span class="dot"></span><b>{T(*DEVICE_STATUS[d["status"]])}</b>',
                 T('BootBridge 网页安装，不用拆机', 'BootBridge web install, no need to open the case')
                 if route == 'web' else T('TTL 串口安装，要拆机', 'TTL serial install, open the case')]
    if d.get('soc'):
        parts.append(esc(d['soc']))
    if d.get('slots'):
        parts.append(esc(T(*MECHANISM[d['slots']['mechanism']])))
    return '<p class="meta">' + '<span class="sep">|</span>'.join(parts) + '</p>'


def device_page(d, releases):
    route = route_of(d)
    steps = web_steps(d) if route == 'web' else ttl_steps(d, route == 'trial')
    out = [f'<p class="crumb"><a href="/devices/">{T("机型", "Models")}</a> / {esc(full_name(d))}</p>',
           f'<h1>{esc(full_name(d))}</h1>']
    al = aliases_of(d)
    if al:
        out.append(f'<p class="sub">{T("也叫", "Also called")} {esc(T("、", " / ").join(al))}</p>')
    if route == 'trial':
        out.append(T('<p class="caution"><strong>未验证，不要写进闪存。</strong>这块板有构建，但还没有人在真机上跑过。'
                     '下面的步骤只把 U-Boot 放进内存里运行一次，断电就回到原样。</p>',
                     '<p class="caution"><strong>Untested; do not write to flash.</strong> This board has a build, but '
                     'nobody has run it on real hardware yet. The steps below only run U-Boot from RAM once; power off '
                     'and the router is unchanged.</p>'))
    out.append(status_line(d, route))
    if d.get('summary'):
        out.append(f'<p>{inline(d["summary"])}</p>')
    for ph in d.get('photos') or []:
        cap = inline(ph.get('caption', ''))
        if ph.get('credit'):
            cap += T(f' <span class="credit">照片：{inline(ph["credit"])}</span>',
                     f' <span class="credit">Photo: {inline(ph["credit"])}</span>')
        out.append(f'<figure class="photo"><img src="/img/{esc(ph["file"])}" alt="{esc(full_name(d))}" loading="lazy">'
                   f'<figcaption>{cap}</figcaption></figure>')
    out.append(f'<div class="facts">{kv_table(facts_of(d, route, releases))}</div>')

    toc = [('install', T('试跑步骤', 'Trial steps') if route == 'trial' else T('安装步骤', 'Install steps'))]
    if route != 'trial':
        toc.append(('after', T('装好以后', 'After installing')))
    if d.get('tested') or d.get('not_tested'):
        toc.append(('tested', T('验证情况', 'Test results')))
    if d.get('hardware'):
        toc.append(('hardware', T('硬件资料', 'Hardware info')))
    if d.get('recovery'):
        toc.append(('recovery', T('出问题怎么办', 'Troubleshooting')))
    out.append(T('<p class="toc-inline">本页：', '<p class="toc-inline">On this page:')
               + ' · '.join(f'<a href="#{i}">{esc(t)}</a>' for i, t in toc) + '</p>')

    if d.get('warnings'):
        out.append(T('<h2 id="warnings">动手前先看</h2>', '<h2 id="warnings">Before you start</h2>'))
        out.append(ul(d['warnings']))
    if d.get('differences'):
        out.append(T('<h2 id="differences">和原厂不一样的地方</h2>', '<h2 id="differences">Differences from stock</h2>'))
        out.append(ul(d['differences']))

    out.append(f'<h2 id="install">{toc[0][1]}</h2>')
    if route == 'ttl':
        out.append(text_block(T('大致流程：接好串口，在原厂 U-Boot 里把新 U-Boot 加载到内存运行（这一步不写闪存），'
                                '在它的救援页里备份整片闪存，最后写入。第一次做，建议先读一遍 [TTL 串口安装](/install/ttl)。',
                                'Overview: connect the serial console, load the new U-Boot into RAM from stock U-Boot '
                                '(no flash writes at this step), back up the whole flash from its rescue page, then write. '
                                'If this is your first time, read [TTL serial install](/install/ttl) first.')))
        out.append(fig_flow())
    elif route == 'trial':
        out.append(text_block(T('下面只把 U-Boot 加载到内存里跑一次，断电就恢复原样。为什么要试跑、要记录什么，'
                                '见 [RAM 试跑](/install/ram-trial)。',
                                'The steps below only run U-Boot from RAM once; power off and the router is unchanged. '
                                'For why to do a trial and what to record, see [RAM trial](/install/ram-trial).')))
    else:
        out.append(text_block(T('BootBridge 借原厂的升级功能装上一个临时的桥接系统，由它备份、核对，再写入 U-Boot。'
                                f'要用的工具是 [BootBridge 网页版]({LINKS["bootbridge"]})；截图和细节见 '
                                '[BootBridge 网页安装](/install/bootbridge)。',
                                'BootBridge uses the stock upgrade function to install a temporary bridge system, which '
                                'backs up, verifies and then writes U-Boot. The tool is the '
                                f'[BootBridge web app]({LINKS["bootbridge"]}); for screenshots and details see '
                                '[BootBridge web install](/install/bootbridge).')))
    out.append(render_steps(steps))

    if route != 'trial':
        out.append(T('<h2 id="after">装好以后</h2>', '<h2 id="after">After installing</h2>'))
        items = []
        if d.get('rescue'):
            r = d['rescue']
            items.append(T(f'进救援页：{r["how"]}，打开 `http://{r.get("address", "192.168.1.1")}`{INCOGNITO_SHORT()}。',
                           f'Enter the rescue page: {r["how"]}, then open '
                           f'`http://{r.get("address", "192.168.1.1")}`{INCOGNITO_SHORT()}.'))
        items.append(T('切换系统：', 'Switch systems: ')
                     + (d.get('slot_select') or T('在救援页里选这次启动哪个系统、默认启动哪个。',
                                                  'In the rescue page, choose which system boots this time and which is the default.')))
        items.append(T('刷第三方固件：见[刷固件与切换系统](/use/firmware)。',
                       'Flash third-party firmware: see [Flash firmware and switch systems](/use/firmware).'))
        items.append(T('升级 U-Boot、回原厂：见[升级 U-Boot、回原厂](/use/upgrade)。',
                       'Upgrade U-Boot or go back to stock: see [Upgrade U-Boot and go back to stock](/use/upgrade).'))
        out.append(ul(items))
        if d.get('slots', {}).get('note'):
            out.append(f'<p>{inline(d["slots"]["note"])}</p>')

    if d.get('tested') or d.get('not_tested'):
        out.append(T('<h2 id="tested">验证情况</h2>', '<h2 id="tested">Test results</h2>'))
        if d.get('tested'):
            out.append(T('<h3>实测通过</h3>', '<h3>Tested and working</h3>'))
            out.append(ul(d['tested']))
        if d.get('not_tested'):
            out.append(T('<h3>还没测</h3>', '<h3>Not tested</h3>'))
            out.append(ul(d['not_tested']))

    if d.get('hardware'):
        out.append(T('<h2 id="hardware">硬件资料</h2>', '<h2 id="hardware">Hardware info</h2>'))
        out.append(kv_table([(h['label'], inline(h['value'])) for h in d['hardware']]))

    if route != 'web':
        out.append(T('<h2 id="shell">系统内安装</h2>', '<h2 id="shell">In-system install</h2>'))
        clue = d.get('shell', {}).get('access')
        out.append(text_block(T('不拆机、在原厂系统里用 Telnet / SSH 安装的方式还在调研，这台机器还没有开放。',
                                'Installing from the stock system over Telnet / SSH without opening the case is still '
                                'being researched and is not available for this model yet.')
                              + (T(f'目前的线索：{clue}', f'Current lead: {clue}') if clue else
                                 T(f'还不知道怎么在它的原厂系统里拿到 root。知道的话欢迎[告诉我们]({LINKS["issues"]})。',
                                   f'We do not know how to get root on its stock system yet. If you do, please '
                                   f'[tell us]({LINKS["issues"]}).'))
                              + T('进展见[系统内安装](/install/shell)。',
                                  'See [In-system install](/install/shell) for progress.')))

    if d.get('recovery'):
        out.append(T('<h2 id="recovery">出问题怎么办</h2>', '<h2 id="recovery">Troubleshooting</h2>'))
        out.append(ul(d['recovery']))
        out.append(text_block(T('更多情况按现象查：[出问题怎么办](/help/)。',
                                'For more cases, search by symptom: [Troubleshooting](/help/).')))

    links = list(d.get('links') or [])
    if route == 'trial' and not any(l['url'] == LINKS['report'] for l in links):
        links.insert(0, {'text': T('提交试跑报告', 'Submit the trial report'), 'url': LINKS['report']})
    if links:
        out.append(T('<h2 id="links">链接</h2>', '<h2 id="links">Links</h2>'))
        out.append(ul(f'[{l["text"]}]({l["url"]})' for l in links))
    return '\n'.join(out)


# ---------------------------------------------------------------- generated blocks

def name_cell(d, link=True):
    n = esc(full_name(d))
    cell = f'<a href="/devices/{d["id"]}">{n}</a>' if link else f'<strong>{n}</strong>'
    al = aliases_of(d)
    if al:
        cell += T(f' <span class="aka">也叫 {esc("、".join(al))}</span>',
                  f' <span class="aka">Also called {esc(" / ".join(al))}</span>')
    return cell


def how_cell(d):
    return T(*{'web': ('BootBridge 网页', 'BootBridge web'),
               'ttl': ('TTL 串口', 'TTL serial'),
               'trial': ('只能 RAM 试跑', 'RAM trial only')}[route_of(d)])


def verified_table(devices):
    rows = [([name_cell(d), how_cell(d), inline(d.get('brief', ''))], f' data-k="{esc(keys_of(d))}"')
            for d in devices if route_of(d) != 'trial']
    return table([T('机型', 'Model'), T('安装方式', 'Install method'), T('说明', 'Notes')], rows, 'devs', {1: 'how'})


def device_list(devices, others):
    ok = [d for d in devices if route_of(d) != 'trial']
    trial = [d for d in devices if route_of(d) == 'trial']
    planned = [m for m in others if m['status'] == 'planned']
    wontdo = [m for m in others if m['status'] == 'wontdo']

    def other_name(m):  # aliases of these are for the filter only
        return esc(m.get('display', m['name']))

    out = []
    out.append(T(f'<section data-group><h2 id="ok"><span class="dot"></span>可以装 <span class="n">{len(ok)}</span></h2>',
                 f'<section data-group><h2 id="ok"><span class="dot"></span>Can be installed <span class="n">{len(ok)}</span></h2>'))
    out.append(T('<p>点机型名进入它的安装步骤。</p>', '<p>Click a model name to see its install steps.</p>'))
    out.append(verified_table(devices) + '</section>')

    out.append(T(f'<section data-group><h2 id="untested"><span class="dot untested"></span>有构建，未验证 <span class="n">{len(trial)}</span></h2>',
                 f'<section data-group><h2 id="untested"><span class="dot untested"></span>Built, untested <span class="n">{len(trial)}</span></h2>'))
    out.append(text_block(T('还没有人在真机上跑过。只给能接 TTL 的人做 [RAM 试跑](/install/ram-trial)，不要写进闪存。',
                            'Nobody has run these on real hardware yet. Only people who can connect TTL should do a '
                            '[RAM trial](/install/ram-trial); do not write to flash.')))
    out.append(table([T('机型', 'Model'), T('说明', 'Notes')],
                     [([name_cell(d), inline(d.get('brief', ''))], f' data-k="{esc(keys_of(d))}"')
                      for d in trial], 'devs') + '</section>')

    out.append(T(f'<section data-group><h2 id="planned"><span class="dot planned"></span>规划中 <span class="n">{len(planned)}</span></h2>',
                 f'<section data-group><h2 id="planned"><span class="dot planned"></span>Planned <span class="n">{len(planned)}</span></h2>'))
    out.append(text_block(T('还没有构建，请不要刷。打算以后支持，下面写了现在卡在哪里。手里有这些机器、能接 TTL 的，'
                            '欢迎[参与收录](/contribute/)。',
                            'No builds yet; please do not flash. We plan to support these; the table shows what is blocking '
                            'each one. If you have one of these models and can connect TTL, please '
                            '[contribute](/contribute/).')))
    out.append(table([T('机型', 'Model'), T('已知情况', 'Known'), T('还缺什么', 'Still needed')],
                     [([other_name(m), inline(m.get('known', '')), inline(m['missing'])],
                       f' id="{esc(anchor_of(m))}" data-k="{esc(keys_of(m))}"')
                      for m in planned], 'devs others') + '</section>')

    if wontdo:
        out.append(T(f'<section data-group><h2 id="wontdo"><span class="dot wontdo"></span>不打算做 <span class="n">{len(wontdo)}</span></h2>',
                     f'<section data-group><h2 id="wontdo"><span class="dot wontdo"></span>Not planned <span class="n">{len(wontdo)}</span></h2>'))
        out.append(table([T('机型', 'Model'), T('原因', 'Reason')], [([other_name(m), inline(m['reason'])],
                                           f' id="{esc(anchor_of(m))}" data-k="{esc(keys_of(m))}"')
                                          for m in wontdo], 'devs') + '</section>')
    out.append(T('<p id="none" hidden>没有匹配的机型。可能还没收录，换个写法试试（只输型号，不带品牌）。</p>',
                 '<p id="none" hidden>No matching models. They may not be listed yet; try another spelling (model name only, without the vendor).</p>'))
    return '\n'.join(out)


def device_filter():
    return T('<p class="filter" hidden><label for="q">按型号筛选</label>'
             '<input id="q" type="search" placeholder="输入型号，例如 VS010、AX6000" autocomplete="off"></p>',
             '<p class="filter" hidden><label for="q">Filter by model</label>'
             '<input id="q" type="search" placeholder="Model, for example VS010 or AX6000" autocomplete="off"></p>')


def home_others(devices, others):
    """Front page: every model that cannot be installed yet, each name a link to its entry."""
    trial = [d for d in devices if route_of(d) == 'trial']
    planned = [m for m in others if m['status'] == 'planned']
    wontdo = [m for m in others if m['status'] == 'wontdo']

    def names(models):
        return ('<ul class="names">' + ''.join(
            f'<li><a href="/devices/#{esc(anchor_of(m))}">{esc(m.get("display", m["name"]))}</a></li>' for m in models) + '</ul>')

    out = []
    if trial:
        out.append(T(f'<h3><span class="dot untested"></span>有构建，未验证 <span class="n">{len(trial)}</span></h3>',
                     f'<h3><span class="dot untested"></span>Built, untested <span class="n">{len(trial)}</span></h3>'))
        out.append(text_block(T('U-Boot 已经编出来了，还没有人在真机上跑过。能接 TTL 的可以做 [RAM 试跑](/install/ram-trial)，'
                                '不要写进闪存。',
                                'U-Boot has been built, but nobody has run it on real hardware yet. If you can connect TTL, '
                                'you can do a [RAM trial](/install/ram-trial); do not write to flash.')))
        out.append(table([T('机型', 'Model'), T('说明', 'Notes')],
                         [([name_cell(d), inline(d.get('brief', ''))], '') for d in trial], 'devs'))
    if planned:
        out.append(T(f'<h3><span class="dot planned"></span>规划中 <span class="n">{len(planned)}</span></h3>',
                     f'<h3><span class="dot planned"></span>Planned <span class="n">{len(planned)}</span></h3>'))
        out.append(text_block(T('还没有构建，请不要刷。点机型名看它现在的已知情况和还缺什么；'
                                '手里有这些机器的，欢迎[参与收录](/contribute/)。',
                                'No builds yet; please do not flash. Click a model name to see what is known and what is '
                                'still needed. If you have one of these models, please [contribute](/contribute/).')))
        out.append(names(planned))
    if wontdo:
        out.append(T(f'<h3><span class="dot wontdo"></span>不打算做 <span class="n">{len(wontdo)}</span></h3>',
                     f'<h3><span class="dot wontdo"></span>Not planned <span class="n">{len(wontdo)}</span></h3>'))
        out.append(text_block(T('这几款不在计划里，点机型名看原因。',
                                'These models are not planned; click a name to see why.')))
        out.append(names(wontdo))
    return '\n'.join(out)


def home_finder():
    """On the front page: a plain form that opens the model list with ?q= filled in."""
    return T('<form class="finder" action="/devices/" method="get" role="search">'
             '<label for="hq">先找你的机型</label>'
             '<div><input id="hq" name="q" type="search" autocomplete="off" '
             'placeholder="路由器底部铭牌上的型号，例如 CR8806、VS010、RT3000">'
             '<button type="submit">查找</button></div></form>',
             '<form class="finder" action="/devices/" method="get" role="search">'
             '<label for="hq">Find your model first</label>'
             '<div><input id="hq" name="q" type="search" autocomplete="off" '
             'placeholder="Model on the label on the bottom of the router, for example CR8806, VS010, RT3000">'
             '<button type="submit">Find</button></div></form>')


def oem_table(devices):
    rows = []
    for d in devices:
        if d['install']['method'] != 'bootbridge':
            continue
        hw = next((h['value'] for h in d.get('hardware') or [] if h['label'] in HW_GROUP), '')
        ver = f'<code>{esc(d["install"]["oem_firmware"])}</code>' + (T('（不用先升级）', ' (no upgrade needed)') if d['install'].get('oem_any') else '')
        rows.append(([name_cell(d), ver, inline(hw)], ''))
    return table([T('机型（铭牌）', 'Model (label)'), T('需要的原厂版本', 'Required stock version'), T('硬件组', 'Hardware group')], rows, 'devs')


def rescue_table(devices):
    rows = [([f'<a href="/devices/{d["id"]}">{esc(full_name(d))}</a>', inline(d['rescue']['how']),
              f'<code>{esc(d["rescue"].get("address", "192.168.1.1"))}</code>'], '')
            for d in devices if d.get('rescue') and route_of(d) != 'trial']
    return table([T('机型', 'Model'), T('怎么进入', 'How to enter'), T('地址', 'Address')], rows, 'devs')


def shell_table(devices):
    rows = [([f'<a href="/devices/{d["id"]}#shell">{esc(full_name(d))}</a>', T(*DEVICE_STATUS[d['status']]),
              inline(d.get('shell', {}).get('access') or T('还不知道', 'Unknown'))], '')
            for d in devices if d['install']['method'] == 'ttl']
    return table([T('机型', 'Model'), T('U-Boot 状态', 'U-Boot status'), T('拿 root 的线索', 'Leads for getting root')], rows, 'devs')


def trial_list(devices):
    return ul(f'[{full_name(d)}](/devices/{d["id"]})' for d in devices if route_of(d) == 'trial')


# ---------------------------------------------------------------- pages

def read_page(path):
    text = path.read_text(encoding='utf-8')
    meta = {}
    if text.startswith('---\n'):
        end = text.index('\n---\n', 4)
        meta = yaml.safe_load(text[4:end]) or {}
        text = text[end + 5:]
    return meta, text


def containers(text):
    """::: note|danger|details [title] ... ::: blocks."""
    out, stack = [], []
    for line in text.split('\n'):
        m = re.match(r'^:::\s*(note|danger|details)\s*(.*)$', line)
        if m:
            kind, title = m.group(1), m.group(2).strip()
            if kind == 'details':
                out += [f'<details markdown="1"><summary>{esc(title or T("详细", "Details"))}</summary>', '']
                stack.append('</details>')
            else:
                out += [f'<div class="note{" danger" if kind == "danger" else ""}" markdown="1">', '']
                if title:
                    out += [f'**{title}**', '']
                stack.append('</div>')
        elif line.strip() == ':::' and stack:
            out += ['', stack.pop(), '']
        else:
            out.append(line)
    if stack:
        raise BuildError('unclosed ::: block')
    return '\n'.join(out)


def render_markdown(text):
    md = markdown.Markdown(
        extensions=['tables', 'fenced_code', 'attr_list', 'md_in_html', 'toc', 'sane_lists'],
        extension_configs={'toc': {'slugify': slugify_unicode}})
    out = md.convert(containers(text))
    return out.replace('<table>', '<div class="tw"><table>').replace('</table>', '</table></div>')


def side_nav(page):
    here = page[:-len('index.html')] if page.endswith('index.html') else page
    if here.startswith('devices/'):
        here = 'devices/'
    out = []
    for title, items in SIDE:
        if title:
            out.append(f'<p class="g">{esc(T(*title))}</p>')
        out.append('<ul>')
        for href, text in items:
            cls = ' class="on"' if target_of(href)[0] == here else ''
            out.append(f'<li><a href="{href}"{cls}>{esc(T(*text))}</a></li>')
        out.append('</ul>')
    out.append(T(f'<p class="contact">QQ 群 {QQ}<br><a href="{LINKS["issues"]}">GitHub Issues</a><br>'
                 f'<a href="{LINKS["sponsor"]}">爱发电</a></p>',
                 f'<p class="contact">QQ group {QQ}<br><a href="{LINKS["issues"]}">GitHub Issues</a><br>'
                 f'<a href="{LINKS["sponsor"]}">Afdian</a></p>'))
    return '\n'.join(out)


def page_toc(body):
    """The page's own <h2> headings, for the right-hand column."""
    heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body, re.S)
    if len(heads) < 2:
        return ''

    def clean(h):
        return re.sub(r'<[^>]+>', '', re.sub(r'<span class="n">.*?</span>', '', h)).strip()

    items = ''.join(f'<li><a href="#{i}">{clean(h)}</a></li>' for i, h in heads)
    return T(f'<aside class="toc" aria-label="本页内容"><p>本页</p><ul>{items}</ul></aside>',
             f'<aside class="toc" aria-label="On this page"><p>On this page</p><ul>{items}</ul></aside>')


def href_of(page):
    """'install/ttl.html' -> 'install/ttl', 'devices/index.html' -> 'devices/'."""
    if page == '404.html':
        return ''
    return page[:-len('index.html')] if page.endswith('index.html') else page[:-len('.html')]


def lang_switch(page):
    """Link to the same page in the other language; /~xx/ is resolved by fix_links."""
    other = 'en' if LANG == 'zh' else 'zh'
    if other not in BUILT:
        return ''
    return (f'<a class="ext lang" href="/~{other}/{href_of(page)}" hreflang="{"en" if other == "en" else "zh-CN"}" '
            f'lang="{"en" if other == "en" else "zh-CN"}">{"English" if other == "en" else "中文"}</a>')


def layout(page, title, body, description='', full_title=None):
    desc = f'\n<meta name="description" content="{esc(description)}">' if description else ''
    return f'''<!doctype html>
<html lang="{T('zh-CN', 'en')}" data-site-lang="{LANG}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title or f"{title} - {NAME}")}</title>{desc}
<link rel="icon" href="/logo.svg" type="image/svg+xml">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<input type="checkbox" id="nav-open" class="nav-open" aria-label="{T('打开目录', 'Open the menu')}">
<header class="top">
<a class="brand" href="/"><img src="/logo.svg" alt="" width="26" height="26">{NAME}<small>{T('安装指南', 'Install guide')}</small></a>
{lang_switch(page)}
<a class="ext" href="{LINKS["repo"]}">GitHub</a>
<label class="menu" for="nav-open">{T('目录', 'Menu')}</label>
</header>
<div class="shell">
<nav class="side" aria-label="{T('目录', 'Contents')}">
{side_nav(page)}
</nav>
<main class="doc">
{body}
<footer class="foot">{T('U-Boot 遵循 GPL-2.0。本项目与各路由器厂商无关。', 'U-Boot is licensed under GPL-2.0. This project is not affiliated with any router vendor.')}</footer>
</main>
{page_toc(body)}
</div>
<script src="/site.js" defer></script>
</body>
</html>
'''


def target_of(href):
    """'/install/ttl#x' -> ('install/ttl.html', '#x'); '/devices/' -> ('devices/', '')."""
    path, hash_, frag = href[1:].partition('#')
    path, q, query = path.partition('?')
    if path and not path.endswith('/') and '.' not in posixpath.basename(path):
        path += '.html'
    return path, (q + query) + (hash_ + frag)


def rel(page, path):
    here = posixpath.dirname(page) or '.'
    if path == '' or path.endswith('/'):
        r = posixpath.relpath(path.rstrip('/') or '.', here)
        return './' if r == '.' else r + '/'
    return posixpath.relpath(path, here)


# Top-level names served once for both languages.
SHARED = {p.name for p in (SITE / 'static').iterdir()} | {'fwunpack'}


def fix_links(page, text):
    """page is the output path ('en/install/ttl.html'). /x links to x in the
    language being built, /~zh/x and /~en/x to a given language, and static
    files are shared."""
    def internal(m):
        attr, href = m.group(1), m.group(2)
        lang = LANG
        if re.match(r'/~(zh|en)/', href):
            lang, href = href[2:4], href[4:]
        path, rest = target_of(href)
        if path.split('/')[0] not in SHARED:
            path = PREFIX[lang] + path
        url = BASE + path if page == '404.html' else rel(page, path)
        return f'{attr}="{url}{rest}"'

    text = re.sub(r'\b(href|src|action)="(/(?!/)[^"]*)"', internal, text)
    return re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noreferrer"', text)


def check_links(out):
    errors, ids = [], {}
    for f in sorted(out.rglob('*.html')):
        page = f.relative_to(out).as_posix()
        if page == '404.html':
            continue
        for m in re.finditer(r'\b(?:href|src)="([^"]+)"', f.read_text(encoding='utf-8')):
            url = html.unescape(m.group(1))
            if re.match(r'^[a-z][a-z0-9+.-]*:', url, re.I):
                continue
            path, _, frag = url.partition('#')
            path = path.split('?')[0]
            target = f if path == '' else (f.parent / path)
            if target.is_dir():
                target = target / 'index.html'
            target = target.resolve()
            if not target.exists():
                errors.append(f'{page}: broken link {url}')
            elif frag and target.suffix == '.html':
                if target not in ids:
                    ids[target] = set(re.findall(r'\bid="([^"]+)"', target.read_text(encoding='utf-8')))
                if frag not in ids[target]:
                    errors.append(f'{page}: no #{frag} in {target.relative_to(out.resolve()).as_posix()}')
    return errors


CJK = re.compile(r'[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]')


def cjk_leaks(root):
    """Chinese left in the visible text of the English pages."""
    errors = []
    for f in sorted(root.rglob('*.html')):
        text = f.read_text(encoding='utf-8')
        text = re.sub(r'<script\b.*?</script>', '', text, flags=re.S)
        # BootBridge's no-JavaScript notice already carries both languages
        text = re.sub(r'<div id="boot-fail".*?</div>', '', text, flags=re.S)
        text = re.sub(r'\b(?:id|href|data-k)="[^"]*"', '', text)
        text = re.sub(r'<a class="ext lang"[^>]*>中文</a>', '', text)
        seen = set()
        for m in CJK.finditer(text):
            line = text.count('\n', 0, m.start()) + 1
            if line in seen:
                continue
            seen.add(line)
            errors.append(f'{f.relative_to(root.parent).as_posix()}:{line}: Chinese in the English page: '
                          f'{text[max(0, m.start() - 30):m.start() + 30]!r}')
    return errors


def redirect_page(page, to):
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={to}">
<link rel="canonical" href="{to}">
<title>{T("页面已移动", "Page moved")} - {NAME}</title>
</head>
<body>
<p>{T("页面已移动到", "The page has moved to")} <a href="{to}">{T("这里", "here")}</a>{T("。", ".")}</p>
</body>
</html>
'''


def fwunpack(devices):
    """One model source: site/devices; config names come from board DTS."""
    root = SITE.parent
    targets = []
    for d in devices:
        capacities = d.get('slots', {}).get('capacities', [])
        for c in capacities:
            if not isinstance(c.get('bytes'), int) or c['bytes'] <= 0 or c['bytes'] % 131072:
                raise BuildError(f"{d['id']}: invalid slot capacity")
        if d['id'].startswith('h3c-'):
            paths = sorted((root / 'u-boot-2016/arch/arm/dts').glob('ipq5018-h3c*.dts'))
        else:
            artifact = d.get('artifact', '').removesuffix('-untested').replace('_', '-', 1)
            paths = [p for p in (root / 'u-boot-2016/arch/arm/dts').glob('*.dts')
                     if norm(p.stem) == norm(artifact)]
            if len(paths) != 1:
                raise BuildError(f"{d['id']}: cannot identify board DTS for unpacker")
        configs = []
        for path in paths:
            if path.is_file():
                for m in re.finditer(r'config_name\s*=([^;]+);', path.read_text()):
                    configs.extend(re.findall(r'"([^"\n]+)"', m.group(1)))
        targets.append({'id': d['id'], 'name': full_name(d), 'slots': capacities,
                        'source': (T('已知系统槽：', 'Known system slots: ')
                                   + T('；', '; ').join(f'{c["name"]} {c["bytes"] / 1048576:g} MiB' for c in capacities)
                                   + T('。请在救援页核对当前布局。', '. Check the current layout in the rescue page.'))
                        if capacities else T('系统槽大小不确定，请在救援页核对实际分区容量。',
                                             'System slot sizes are uncertain; check the actual partition sizes in the rescue page.'),
                        'configs': sorted(set(configs))})
    options = ''.join(f'<option value="{esc(t["id"])}">{esc(t["name"])}</option>' for t in targets)
    data = json.dumps(targets, ensure_ascii=False).replace('<', '\\u003c')
    panel = root / 'tools/fwunpack' / T('panel.html', 'panel.en.html')
    return panel.read_text().replace('@@OPTIONS@@', options).replace('@@TARGETS@@', data)


def build(out, langs=LANGS):
    global LANG, BUILT
    BUILT = langs
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE / 'static', out)
    (out / 'fwunpack').mkdir()
    for name in ('core.js', 'app.js'):
        shutil.copyfile(SITE.parent / 'tools/fwunpack' / name, out / 'fwunpack' / name)
    n = 0
    try:
        for LANG in langs:
            n += build_lang(out)
    finally:
        LANG = 'zh'
    errors = check_links(out)
    if 'en' in langs:
        errors += cjk_leaks(out / 'en')
    if errors:
        raise BuildError('\n'.join(errors))
    return n


def build_lang(out):
    """The pages of one language (LANG) under out/PREFIX[LANG]."""
    prefix = PREFIX[LANG]
    devices = load_devices()
    others = load_others()
    releases = load_releases()
    counts = {
        'n_verified': sum(route_of(d) != 'trial' for d in devices),
        'n_untested': sum(route_of(d) == 'trial' for d in devices),
        'n_planned': sum(m['status'] == 'planned' for m in others),
        'n_wontdo': sum(m['status'] == 'wontdo' for m in others),
    }
    blocks = {
        'verified_table': lambda: verified_table(devices),
        'device_filter': device_filter,
        'home_finder': home_finder,
        'home_others': lambda: home_others(devices, others),
        'fig_flow': fig_flow,
        'fig_flash': fig_flash,
        'fig_wiring': fig_wiring,
        'device_list': lambda: device_list(devices, others),
        'oem_table': lambda: oem_table(devices),
        'rescue_table': lambda: rescue_table(devices),
        'shell_table': lambda: shell_table(devices),
        'trial_list': lambda: trial_list(devices),
        'fwunpack': lambda: fwunpack(devices),
    }

    from bootbridge import build_bootbridge
    try:
        build_bootbridge(out / prefix / 'bootbridge', layout, lambda p, t: fix_links(prefix + p, t), LANG)
    except (ValueError, subprocess.CalledProcessError) as e:
        raise BuildError(f'BootBridge: {e}') from e
    pages = {}

    if LANG != 'zh':
        want = {p.relative_to(SITE / 'pages') for p in (SITE / 'pages').rglob('*.md')}
        have = {p.relative_to(src_dir('pages')) for p in src_dir('pages').rglob('*.md')}
        if want != have:
            raise BuildError(f'{LANG}/pages: missing {sorted(map(str, want - have))}, extra {sorted(map(str, have - want))}')
    for src in sorted(src_dir('pages').rglob('*.md')):
        page = src.relative_to(src_dir('pages')).with_suffix('.html').as_posix()
        meta, text = read_page(src)
        if not meta.get('title'):
            raise BuildError(f'pages/{src.relative_to(SITE / "pages")}: no title')

        def count(m):
            if m.group(1) not in counts:
                raise BuildError(f'{page}: unknown {{{{{m.group(1)}}}}}')
            return str(counts[m.group(1)])

        text = re.sub(r'\{\{(n_\w+)\}\}', count, text)
        body = render_markdown(text)

        def block(m):
            if m.group(1) not in blocks:
                raise BuildError(f'{page}: unknown {{{{{m.group(1)}}}}}')
            return blocks[m.group(1)]()

        body = re.sub(r'<p>\{\{(\w+)\}\}</p>', block, body)
        if '{{' in body:
            raise BuildError(f'{page}: placeholder not on a line of its own')
        pages[page] = layout(page, meta['title'], body, meta.get('description', ''), meta.get('full_title'))

    for d in devices:
        page = f'devices/{d["id"]}.html'
        desc = T(f'{full_name(d)} 安装本项目 U-Boot 的步骤、下载和验证情况。',
                 f'Steps, downloads and test results for installing this project\'s U-Boot on {full_name(d)}.')
        pages[page] = layout(page, full_name(d), device_page(d, releases), desc)

    if LANG == 'zh':  # GitHub Pages serves one 404 for the whole site
        pages['404.html'] = layout('404.html', T('页面不存在', 'Page not found'),
                                   T('<h1>页面不存在</h1>\n'
                                     '<p>链接可能已经变了。可以从<a href="/">首页</a>或<a href="/devices/">机型列表</a>重新找。</p>\n',
                                     '<h1>Page not found</h1>\n'
                                     '<p>The link may have changed. Start again from the <a href="/">Home</a> page or the '
                                     '<a href="/devices/">Model list</a>.</p>\n')
                                   + '<p lang="en">Page not found. Start again from the <a href="/~en/">English home page</a>.</p>')

    for page, text in pages.items():
        f = out / prefix / page
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(fix_links(prefix + page, text), encoding='utf-8')

    for page, to in (REDIRECTS.items() if LANG == 'zh' else ()):
        if page in pages:
            raise BuildError(f'redirect {page} would overwrite a page')
        path, rest = target_of(to)
        f = out / page
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(redirect_page(page, rel(page, path) + rest), encoding='utf-8')
    return len(pages) + (len(REDIRECTS) if LANG == 'zh' else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', type=Path, default=SITE / 'dist', help='output directory (default: site/dist)')
    ap.add_argument('--langs', default=','.join(LANGS), help='languages to build (default: zh,en)')
    args = ap.parse_args()
    try:
        n = build(args.out.resolve(), tuple(args.langs.split(',')))
    except BuildError as e:
        print(f'build failed:\n{e}', file=sys.stderr)
        return 1
    print(f'{n} pages -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
