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

Links inside the site are written as /path (no .html, no base) in pages and in
the YAML; the build turns them into relative links and fails on any link or
#anchor that does not exist. Pages work without JavaScript: static/site.js
only adds the model filter, the copy buttons and the current-heading mark.

devices/<id>.yaml fields
    id, vendor, name           required; id = file name
    status                     verified | community | untested
    install.method             bootbridge | ttl
    install.oem_firmware       bootbridge only: the stock version BootBridge needs
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
import posixpath
import re
import shutil
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
    'bootbridge': 'https://flyfish-go.github.io/H3C-NX30-Uboot/',
    'h3c_release': 'https://github.com/FlyFish-go/H3C-NX30-Uboot/releases/tag/uboot-v0.1.0',
    'sponsor': 'https://ifdian.net/a/FlyFish-go',
}
QQ = '1131957442'

SIDE = [  # (group title or None, [(link, text)])
    (None, [('/', '首页'), ('/devices/', '机型列表')]),
    ('安装', [('/install/', '选哪种方式'),
              ('/install/bootbridge', 'BootBridge 网页安装'),
              ('/install/ttl', 'TTL 串口安装'),
              ('/install/ram-trial', 'RAM 试跑'),
              ('/install/shell', '系统内安装')]),
    ('装好以后', [('/use/rescue', '进入救援页'),
                  ('/use/firmware', '刷固件与切换系统'),
                  ('/use/upgrade', '升级 U-Boot、回原厂')]),
    ('帮助', [('/help/', '出问题怎么办'),
              ('/learn/slots', '双系统怎么切换'),
              ('/learn/glossary', '名词解释')]),
    ('项目', [('/contribute/', '参与收录'), ('/about', '关于')]),
]

# Old URLs that must keep working.
REDIRECTS = {
    'guide/index.html': '/devices/',
    'guide/rescue.html': '/use/rescue',
    'guide/recovery.html': '/help/',
    'concepts/slots.html': '/learn/slots',
    'devices/research.html': '/devices/#planned',
}

DEVICE_STATUS = {'verified': '已验证', 'community': '社区验证', 'untested': '未验证'}
OTHER_STATUS = ('planned', 'wontdo')
MECHANISM = {
    'bootconfig': 'BOOTCONFIG 双系统',
    'xiaomi-env': '小米环境变量双系统',
    'tp-env': 'TP-Link 环境变量双系统',
    'linksys-env': 'Linksys 环境变量双系统',
    'single': '单系统',
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


def load_devices():
    devices = []
    for path in sorted((SITE / 'devices').glob('*.yaml')):
        where = f'devices/{path.name}'
        d = load_yaml(path)
        if not isinstance(d, dict):
            raise BuildError(f'{where}: empty or not a mapping')
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
        devices.append(d)
    devices.sort(key=lambda d: (d.get('order', 999), d['id']))
    return devices


def load_others():
    raw = load_yaml(SITE / 'data' / 'others.yaml') or {}
    models = raw.get('models') or []
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
    return '|'.join(norm(p) for p in parts if p)


def aliases_of(d):
    return [a for a in d.get('aliases') or [] if a != d['name']]


# ---------------------------------------------------------------- drawings

def fig_flow():
    """The TTL install in five stages; only the fourth writes flash."""
    stages = [
        ('', '接串口', '进入原厂 U-Boot 的命令行'),
        ('', '内存里运行', 'TFTP 传入新 U-Boot，不写闪存'),
        ('', '备份', '在救援页下载整片闪存'),
        (' class="w"', '写入', '两份 APPSBL，写完读回核对'),
        ('', '重启确认', '新 U-Boot 照常启动原厂系统'),
    ]
    items = ''.join(f'<li{c}><b>{esc(t)}</b>{esc(x)}</li>' for c, t, x in stages)
    return (f'<ol class="flow">{items}</ol>\n'
            '<p class="figcap">前三步不写闪存，断电就回到原样。只有第 4 步改动闪存。</p>')


def fig_flash():
    """Which partitions an install rewrites."""
    segs = [
        ('', 'SBL1 等', '更前面的启动程序，不动'),
        (' new', 'APPSBL', '换成本项目的 U-Boot'),
        (' new', 'APPSBL_1', '备用的一份，一起换'),
        ('', 'ART', '无线校准数据，不动'),
        (' big', 'rootfs', '系统一，不动'),
        (' big', 'rootfs_1', '系统二，不动'),
    ]
    items = ''.join(f'<div class="seg{c}"><b>{esc(t)}</b>{esc(x)}</div>' for c, t, x in segs)
    return (f'<div class="flash" role="img" aria-label="闪存分区示意：只有 APPSBL 和 APPSBL_1 被替换">{items}</div>\n'
            '<p class="figcap">闪存分区示意，不按比例。各机型的分区名称、数量和顺序不一样；单系统机型没有 rootfs_1。</p>')


def fig_wiring():
    """Three wires between the router pads and the USB-TTL board."""
    rows = [  # y, router pin, adapter pin, kind
        (66, 'GND', 'GND', 'gnd'),
        (104, 'TX', 'RX', 'out'),
        (142, 'RX', 'TX', 'in'),
        (180, 'VCC', 'VCC', 'no'),
    ]
    out = ['<svg class="wiring" viewBox="0 0 560 214" role="img" '
           'aria-label="接线：GND 接 GND，路由器 TX 接串口板 RX，路由器 RX 接串口板 TX，VCC 不接">',
           '<rect class="board" x="16" y="34" width="176" height="170" rx="6"/>',
           '<rect class="board" x="368" y="34" width="176" height="170" rx="6"/>',
           '<text class="cap" x="16" y="22">路由器主板</text>',
           '<text class="cap" x="368" y="22">USB 转 TTL 串口板</text>']
    for y, a, b, kind in rows:
        out.append(f'<text class="pin" x="150" y="{y + 5}" text-anchor="end">{a}</text>')
        out.append(f'<text class="pin" x="410" y="{y + 5}">{b}</text>')
        if kind == 'no':
            out.append(f'<text class="no" x="280" y="{y + 5}" text-anchor="middle">不接</text>')
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
    return ('\n'.join(out) + '\n<p class="figcap">箭头是数据方向：一边的 TX（发）接另一边的 RX（收）。'
            '串口板上的 VCC、3V3、5V 都不接。</p>')


FIGS = {'flow': fig_flow, 'flash': fig_flash, 'wiring': fig_wiring}


# ---------------------------------------------------------------- install steps

def ttl_steps(d, trial):
    a = d['artifact']
    ram, mbn = f'{a}-ram.uimg', f'{a}.mbn'
    t = d.get('ttl') or {}
    n = d.get('notes') or {}
    fdt = t.get('fdt')
    steps = []

    steps.append(dict(id='prepare', title='准备工具和文件', note=n.get('prepare'), body='\n'.join([
        '- USB 转 TTL 串口板，要能用 1.8 V 电平。不少 CH340、CH343、FT232 板子有电平跳线；'
        '只有 3.3 V 的板子要再加一块电平转换。'
        + (f'本机型样机实测是 {t["voltage"]}。' if t.get('voltage') else ''),
        '- 杜邦线 3 根、网线 1 根，拆机用的螺丝刀和撬片。',
        '- 电脑上装好串口终端（PuTTY 或 MobaXterm）和 TFTP 服务器（Windows 用 Tftpd64）。',
        f'- 试跑文件 `{ram}`，见上面表格里的「下载」。' if trial else
        f'- 本机型的两个文件：`{ram}`（在内存里试跑，先用它）和 `{mbn}`（写进闪存的正式版），'
        '见上面表格里的「下载」。放进同一个文件夹。',
    ])))

    steps.append(dict(id='wire', title='拆机，接三根线', note=n.get('wire'), body='\n'.join([
        '拆开外壳，在主板上找标着 GND、TX、RX（有时还有 VCC）的 4 个焊盘或排针'
        + (f'（串口在 {t["pins"]}）' if t.get('pins') else '') + '。只接三根线：',
        '',
        '- 路由器 GND 接串口板 GND',
        '- 路由器 TX 接串口板 RX',
        '- 路由器 RX 接串口板 TX',
        '',
        '**VCC 不要接**，路由器用自己的电源。串口终端设成 115200、8N1、无流控。'
        '找焊盘的方法见 [TTL 串口安装](/install/ttl#接线)。',
    ]), fig='wiring', warn='电平接错可能烧坏主芯片的串口脚。没把握时，先用万用表量路由器 TX 对 GND 的电压：'
             '通电后在 1.8 V 左右，就必须用 1.8 V 电平。'))

    steps.append(dict(id='network', title='电脑接网线，设好地址', note=n.get('network'), body='\n'.join([
        f'网线一头接电脑，一头接路由器：{t.get("port", "LAN 口")}。把电脑的有线网卡手动设成：',
        '',
        '- IP 地址 `192.168.1.2`',
        '- 子网掩码 `255.255.255.0`',
        '- 网关、DNS 留空',
        '',
        '打开 Tftpd64，「Current Directory」选放文件的文件夹，「Server interfaces」选 `192.168.1.2`。'
        'Windows 防火墙弹窗时点「允许」。详细设置见 [TTL 串口安装](/install/ttl#电脑设置)。',
    ])))

    steps.append(dict(
        id='interrupt', title='截停原厂 U-Boot', note=n.get('interrupt'),
        body='串口终端打开串口板对应的 COM 口，再给路由器通电。启动信息开始滚动后，看到 '
             '`Hit any key to stop autoboot` 时'
             + (f'：{t["interrupt"]}' if t.get('interrupt') else '马上按一下回车')
             + '。停在命令提示符下就对了。',
        expect=f'Hit any key to stop autoboot:  0\n{t.get("prompt", "IPQ5018#")}',
        expect_note=None if t.get('prompt') else '提示符的名字各机型不一样，停在提示符下就行。',
        fail='\n'.join([
            '- **一个字都没有**：TX、RX 可能接反了，对调再试；检查 GND 接了没有、COM 口选对没有。',
            '- **全是乱码**：波特率不是 115200，或者电平不对。',
            '- **来不及按**：通电前就按住回车不放，看到提示符再松开。',
            '- **能看不能输入**：路由器 RX 那根线没接好，或者 RX 脚被电阻拉到了地'
            '（例如 [TCL T30 Pro](/devices/tcl-t30-pro)）。',
        ])))

    steps.append(dict(
        id='fdt', title='记下设备树地址', note=n.get('fdt'),
        body='下一步要用到原厂 U-Boot 的设备树地址。执行下面这条命令，记下等号后面的值。这一步只读，不改任何东西。',
        cmd='printenv fdtcontroladdr',
        expect=f'fdtcontroladdr={fdt[2:] if fdt else "4a9……"}',
        expect_note='这是我们样机上的值，你的机器以屏幕上显示的为准。' if fdt else '每种机型不一样，不要照抄别人的地址。',
        fail='- **提示没有这个变量**：执行 `bdinfo`，找 `fdt_blob` 那一行的地址。'))

    steps.append(dict(
        id='ramboot', title='在内存里运行新 U-Boot', note=n.get('ramboot'),
        body='逐行输入下面四条命令'
             + ('' if fdt else '，最后一行的地址换成上一步记下的值（前面加 `0x`）')
             + '。新 U-Boot 只在内存里运行，**不写闪存**，断电就回到原样。',
        cmd='\n'.join([
            'setenv ipaddr 192.168.1.1',
            'setenv serverip 192.168.1.2',
            f'tftpboot 0x44000000 {ram}',
            f'bootm 0x44000000 - {fdt or "<上一步的地址>"}',
        ]),
        expect='\n'.join([
            'Bytes transferred = ……',
            '## Booting kernel from Legacy Image at 44000000 ...',
            'Starting kernel ...',
            '',
            'U-Boot 2016.01-……',
        ] + (['UNTESTED BOARD: not verified on hardware'] if trial else [])),
        expect_note='中间还有很多行，大致是这个顺序。',
        fail='\n'.join([
            '- **一直打印 `T T T` 或 `TFTP error`**：检查电脑 IP 是不是 `192.168.1.2`，Tftpd64 有没有选对网卡和文件夹，'
            '防火墙有没有放行；网线换一个 LAN 口试试。',
            '- **`Wrong Image Format`**：文件用错了，这里要用 `-ram.uimg`，不是 `.mbn`。',
            '- **打印 `Booting restricted without authentication!!` 然后重启**：这台机器开了安全启动，'
            '**不能安装**，到此为止。',
            '- **停在 `Starting kernel ...` 不动**：设备树地址写错了，回上一步核对。',
        ])))

    steps.append(dict(
        id='rescue', title='打开救援页', note=n.get('rescue'),
        body='新 U-Boot 起来后也会倒计时，再按一次回车截停，然后输入 `httpd`。浏览器打开 `http://192.168.1.1`。'
             + ('\n\n**只看，不写**：不要点「写入」「更新」一类的按钮，也不要在串口里执行 `saveenv`、`nand write`、'
                '`bootconfig set`。逐项记下：每个网口能不能打开救援页、「系统信息」里的闪存型号、各个 LED 和按键的表现。'
                if trial else ''),
        cmd='httpd',
        check='浏览器里出现救援页。' if trial else f'浏览器里出现救援页，「系统信息」里的型号是 {full_name(d)}。',
        fail='\n'.join([
            '- **网页打不开**：确认电脑 IP 还是 `192.168.1.2`；关掉代理和 VPN；一次只接一根网线，换一个 LAN 口试试。',
        ] + ([] if trial else ['- **型号不对**：马上断电，不要继续，到 Issue 反馈。']))))

    if trial:
        steps.append(dict(
            id='report', title='提交试跑报告，然后断电',
            body=f'不管成功还是失败，都请用[试跑报告表单]({LINKS["report"]})告诉我们：机型和铭牌上的硬件版本、启动日志、'
                 '闪存型号、每个网口能不能打开救援页、LED 和按键的表现。日志里的 MAC 和序列号先打码。'
                 '一块板要靠这样的报告才能改成「已验证」。\n\n'
                 '最后断电再通电，路由器照常启动原厂系统。整个过程没有写过闪存。',
            warn='试跑一切正常也不代表可以刷入。等维护者确认、改成「已验证」以后再说。'))
        return steps

    steps.append(dict(
        id='backup', title='备份整片闪存', note=n.get('backup'),
        body='在救援页「闪存备份」里下载整片闪存，保存到电脑，再复制一份到 U 盘或网盘。'
             '以后想回原厂、或者出问题求助，都要靠这份备份。',
        warn='备份里有这台机器的校准数据（ART）、MAC 和序列号。只留给自己，不要发到群里或 Issue。',
        stop='没拿到完整备份之前，不要做下一步。'))

    steps.append(dict(
        id='flash', title='写入 U-Boot', note=n.get('flash'),
        body=f'打开救援页「U-Boot 更新」，选择 `{mbn}`（不是 `-ram.uimg`），确认写入。'
             '两份 APPSBL 会一起写入，写完自动读回核对。',
        check='页面提示写入成功。',
        warn='写入的十几秒里不要断电，也不要关网页。',
        fail='\n'.join([
            '- **页面拒绝这个文件**：确认是本机型的 `.mbn`，再核对文件的 SHA-256。不要拿别的机型的文件硬刷。',
            '- **写到一半报错**：先别断电，截图到 QQ 群或 Issue 求助。新 U-Boot 还在内存里运行，可以重新写。',
        ])))

    r = d.get('rescue')
    steps.append(dict(
        id='verify', title='断电重启，确认装好', note=n.get('verify'),
        body='断电，等几秒再通电。串口里应该出现新 U-Boot 的版本信息，然后照常进入原厂系统。'
             + (f'以后要进救援页：{r["how"]}，打开 `http://{r.get("address", "192.168.1.1")}`。' if r else ''),
        expect='U-Boot 2016.01-……',
        expect_note='版本号后面跟着提交号和日期，和第 6 步在内存里运行的那个一样。',
        fail='\n'.join([
            '- **还是原厂 U-Boot 的信息**：写入没有生效，回到第 6 步重来。',
            '- **新 U-Boot 起来了，系统起不来**：截停后输入 `httpd` 进救援页，见[出问题怎么办](/help/)。',
        ])))
    return steps


def web_steps(d):
    oem = d['install']['oem_firmware']
    n = d.get('notes') or {}
    r = d.get('rescue') or {}
    return [
        dict(id='model', title='确认机型', note=n.get('model'),
             body=f'看路由器底部铭牌，型号是 {d["name"]}'
                  + (f' 或 {"、".join(aliases_of(d))}' if aliases_of(d) else '')
                  + '。全程不用拆机，只要一台有网线口的电脑和一根网线。'),
        dict(id='oem', title=f'原厂系统升级到 {oem}', note=n.get('oem'),
             body=f'BootBridge 只认这一个官方版本。打开 [BootBridge 网页版]({LINKS["bootbridge"]})，选好机型，'
                  f'第 2 步会给出官方固件的下载地址。登录路由器的原厂后台，在系统升级里先升级到 `{oem}`。'
                  '已经是这个版本的可以跳过。',
             check=f'原厂后台显示的版本号是 `{oem}`。'),
        dict(id='bridge', title='生成桥接包', note=n.get('bridge'),
             body='回到 BootBridge，载入同一份官方固件，生成桥接包。固件只在你的浏览器里处理，不会上传。',
             fail=f'- **提示版本或校验不对**：下载的不是 `{oem}`，或者文件没下完整，重新下载。'),
        dict(id='upload', title='在原厂后台上传桥接包', note=n.get('upload'),
             body='在原厂后台的系统升级里上传桥接包，路由器会重启进入桥接系统。',
             warn='`appsbl.mbn` 这类 U-Boot 文件不能直接传到原厂升级页。第一次安装只能走 BootBridge。'),
        dict(id='install', title='识别、备份、安装', note=n.get('install'),
             body='电脑用网线接路由器的 LAN 口，网卡设为自动获取地址，浏览器打开 `http://192.168.10.1`，'
                  '依次点「识别」「备份」「安装」。\n\n'
                  '备份文件保存在自己电脑上，里面有本机的校准数据和序列号，不要发给别人。'
                  '装完路由器会重启，照常进入原厂系统。',
             stop='备份文件没保存好之前，不要点「安装」。',
             fail='\n'.join([
                 '- **打不开 `192.168.10.1`**：看电脑有没有拿到 `192.168.10.x` 的地址；换一个 LAN 口；等一分钟再刷新。',
                 '- **识别不通过**：不要换别的机型的文件硬装，截图到 QQ 群或 Issue。',
             ])),
        dict(id='upgrade', title='升级到 U-Boot v0.1.0', note=n.get('upgrade'),
             body='BootBridge 装的是较早的 U-Boot（pre.5）。断电，按住 Reset 再通电，约 3 秒后松开，'
                  '打开 `http://192.168.10.1` 进救援页。在「系统信息」看「硬件系列」（HW-A、B、C、D），'
                  '下载对应的 `uboot-v0.1.0-HW-X.zip`，按 '
                  f'[v0.1.0 发布说明]({LINKS["h3c_release"]})「升级」一节，在「U-Boot 更新」里写入。',
             check='重启后，救援页「系统信息」里的 U-Boot 版本带 `v0.1.0`。'),
        dict(id='verify', title='记住怎么进救援页', note=n.get('verify'),
             body=f'以后进救援页：{r.get("how", "按住 Reset 通电")}，打开 `http://{r.get("address", "192.168.10.1")}`。'
                  + (f'\n\n用按键切换系统：{d["slot_select"]}' if d.get('slot_select') else '')
                  + '\n\n要刷第三方固件，见[刷固件与切换系统](/use/firmware)。'),
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
            out.append(f'<p class="thisdev"><strong>本机型：</strong>{inline(s["note"])}</p>')
        if s.get('cmd'):
            out.append(term('在串口里输入', s['cmd']))
        if s.get('expect'):
            out.append(term('应该看到', s['expect'], out=True))
            if s.get('expect_note'):
                out.append(f'<p class="hint">{inline(s["expect_note"])}</p>')
        if s.get('check'):
            out.append(f'<p><span class="label">应该看到：</span>{inline(s["check"])}</p>')
        if s.get('warn'):
            out.append(f'<p class="warn"><strong>注意：</strong>{inline(s["warn"])}</p>')
        if s.get('stop'):
            out.append(f'<p><strong>{inline(s["stop"])}</strong></p>')
        if s.get('fail'):
            out.append(f'<details><summary>不对的话</summary>\n{text_block(s["fail"])}\n</details>')
        out.append('</li>')
    out.append('</ol>')
    return '\n'.join(out)


# ---------------------------------------------------------------- device pages

def download_cell(d, route, releases):
    if route == 'web':
        return (f'安装不用单独下载，BootBridge 会写入 U-Boot。以后升级用 '
                f'<a href="{LINKS["h3c_release"]}">v0.1.0 发布页</a>里的 '
                '<code>uboot-v0.1.0-HW-X.zip</code>，X 是救援页「系统信息」里的硬件系列。')
    a = d['artifact']
    files = f'<code>{esc(a)}-ram.uimg</code>' + ('' if route == 'trial' else f' 和 <code>{esc(a)}.mbn</code>')
    rel = releases.get(a)
    if rel:
        return (f'<a href="{esc(rel["url"])}">{esc(rel["tag"])} 发布页</a>：{files}。'
                '下载后核对 SHA-256（Windows：<code>certutil -hashfile 文件名 SHA256</code>）。')
    zipname = re.sub(r'-untested$', '', a)
    return (f'还没有正式发布。<a href="{LINKS["ci"]}">GitHub Actions</a> 最新一次成功的构建里有 '
            f'<code>{esc(zipname)}</code>（zip，下载要登录 GitHub），里面是 {files}。')


def facts_of(d, route, releases):
    t = d.get('ttl') or {}
    rows = []
    if route == 'web':
        rows.append(('安装方式', inline('[BootBridge 网页安装](/install/bootbridge)，不用拆机')))
        rows.append(('需要的原厂版本', f'<code>{esc(d["install"]["oem_firmware"])}</code>'))
    else:
        rows.append(('安装方式', inline('[TTL 串口安装](/install/ttl)，要拆机') if route == 'ttl'
                     else inline('[RAM 试跑](/install/ram-trial)：要拆机接 TTL，不写闪存')))
        rows.append(('串口', esc('，'.join(x for x in ('115200 8N1', t.get('voltage'), t.get('pins')) if x))))
        rows.append(('截停原厂 U-Boot', inline(t.get('interrupt') or '看到 `Hit any key` 时按回车')))
        rows.append(('设备树地址', inline(f'`{t["fdt"]}`（样机实测）') if t.get('fdt')
                     else inline('没人测过，以 `printenv fdtcontroladdr` 为准')))
    r = d.get('rescue')
    if r:
        rows.append(('进救援页', inline(f'{r["how"]}，打开 `http://{r.get("address", "192.168.1.1")}`')))
    for h in d.get('hardware') or []:
        if h['label'] == '硬件组':
            rows.append(('硬件组', inline(h['value'])))
    rows.append(('下载', download_cell(d, route, releases)))
    return rows


def status_line(d, route):
    if route == 'trial':
        parts = ['<span class="dot untested"></span><b>未验证</b>', '只能 RAM 试跑，不写闪存']
    else:
        parts = [f'<span class="dot"></span><b>{DEVICE_STATUS[d["status"]]}</b>',
                 'BootBridge 网页安装，不用拆机' if route == 'web' else 'TTL 串口安装，要拆机']
    if d.get('soc'):
        parts.append(esc(d['soc']))
    if d.get('slots'):
        parts.append(esc(MECHANISM[d['slots']['mechanism']]))
    return '<p class="meta">' + '<span class="sep">|</span>'.join(parts) + '</p>'


def device_page(d, releases):
    route = route_of(d)
    steps = web_steps(d) if route == 'web' else ttl_steps(d, route == 'trial')
    out = [f'<p class="crumb"><a href="/devices/">机型</a> / {esc(full_name(d))}</p>',
           f'<h1>{esc(full_name(d))}</h1>']
    al = aliases_of(d)
    if al:
        out.append(f'<p class="sub">也叫 {esc("、".join(al))}</p>')
    if route == 'trial':
        out.append('<p class="caution"><strong>未验证，不要写进闪存。</strong>这块板有构建，但还没有人在真机上跑过。'
                   '下面的步骤只把 U-Boot 放进内存里运行一次，断电就回到原样。</p>')
    out.append(status_line(d, route))
    if d.get('summary'):
        out.append(f'<p>{inline(d["summary"])}</p>')
    for ph in d.get('photos') or []:
        cap = inline(ph.get('caption', ''))
        if ph.get('credit'):
            cap += f' <span class="credit">照片：{inline(ph["credit"])}</span>'
        out.append(f'<figure class="photo"><img src="/img/{esc(ph["file"])}" alt="{esc(full_name(d))}" loading="lazy">'
                   f'<figcaption>{cap}</figcaption></figure>')
    out.append(f'<div class="facts">{kv_table(facts_of(d, route, releases))}</div>')

    toc = [('install', '试跑步骤' if route == 'trial' else '安装步骤')]
    if route != 'trial':
        toc.append(('after', '装好以后'))
    if d.get('tested') or d.get('not_tested'):
        toc.append(('tested', '验证情况'))
    if d.get('hardware'):
        toc.append(('hardware', '硬件资料'))
    if d.get('recovery'):
        toc.append(('recovery', '出问题怎么办'))
    out.append('<p class="toc-inline">本页：' + ' · '.join(f'<a href="#{i}">{esc(t)}</a>' for i, t in toc) + '</p>')

    if d.get('warnings'):
        out.append('<h2 id="warnings">动手前先看</h2>')
        out.append(ul(d['warnings']))
    if d.get('differences'):
        out.append('<h2 id="differences">和原厂不一样的地方</h2>')
        out.append(ul(d['differences']))

    out.append(f'<h2 id="install">{toc[0][1]}</h2>')
    if route == 'ttl':
        out.append(text_block('大致流程：接好串口，在原厂 U-Boot 里把新 U-Boot 加载到内存运行（这一步不写闪存），'
                              '在它的救援页里备份整片闪存，最后写入。第一次做，建议先读一遍 [TTL 串口安装](/install/ttl)。'))
        out.append(fig_flow())
    elif route == 'trial':
        out.append(text_block('下面只把 U-Boot 加载到内存里跑一次，断电就恢复原样。为什么要试跑、要记录什么，'
                              '见 [RAM 试跑](/install/ram-trial)。'))
    else:
        out.append(text_block('BootBridge 借原厂的升级功能装上一个临时的桥接系统，由它备份、核对，再写入 U-Boot。'
                              f'要用的工具是 [BootBridge 网页版]({LINKS["bootbridge"]})；截图和细节见 '
                              '[BootBridge 网页安装](/install/bootbridge)。'))
    out.append(render_steps(steps))

    if route != 'trial':
        out.append('<h2 id="after">装好以后</h2>')
        items = []
        if d.get('rescue'):
            r = d['rescue']
            items.append(f'进救援页：{r["how"]}，打开 `http://{r.get("address", "192.168.1.1")}`。')
        items.append('切换系统：' + (d.get('slot_select') or '在救援页里选这次启动哪个系统、默认启动哪个。'))
        items.append('刷第三方固件：见[刷固件与切换系统](/use/firmware)。')
        items.append('升级 U-Boot、回原厂：见[升级 U-Boot、回原厂](/use/upgrade)。')
        out.append(ul(items))
        if d.get('slots', {}).get('note'):
            out.append(f'<p>{inline(d["slots"]["note"])}</p>')

    if d.get('tested') or d.get('not_tested'):
        out.append('<h2 id="tested">验证情况</h2>')
        if d.get('tested'):
            out.append('<h3>实测通过</h3>')
            out.append(ul(d['tested']))
        if d.get('not_tested'):
            out.append('<h3>还没测</h3>')
            out.append(ul(d['not_tested']))

    if d.get('hardware'):
        out.append('<h2 id="hardware">硬件资料</h2>')
        out.append(kv_table([(h['label'], inline(h['value'])) for h in d['hardware']]))

    if route != 'web':
        out.append('<h2 id="shell">系统内安装</h2>')
        clue = d.get('shell', {}).get('access')
        out.append(text_block('不拆机、在原厂系统里用 Telnet / SSH 安装的方式还在调研，这台机器还没有开放。'
                              + (f'目前的线索：{clue}' if clue else
                                 f'还不知道怎么在它的原厂系统里拿到 root。知道的话欢迎[告诉我们]({LINKS["issues"]})。')
                              + '进展见[系统内安装](/install/shell)。'))

    if d.get('recovery'):
        out.append('<h2 id="recovery">出问题怎么办</h2>')
        out.append(ul(d['recovery']))
        out.append(text_block('更多情况按现象查：[出问题怎么办](/help/)。'))

    links = list(d.get('links') or [])
    if route == 'trial' and not any(l['url'] == LINKS['report'] for l in links):
        links.insert(0, {'text': '提交试跑报告', 'url': LINKS['report']})
    if links:
        out.append('<h2 id="links">链接</h2>')
        out.append(ul(f'[{l["text"]}]({l["url"]})' for l in links))
    return '\n'.join(out)


# ---------------------------------------------------------------- generated blocks

def name_cell(d, link=True):
    n = esc(full_name(d))
    cell = f'<a href="/devices/{d["id"]}">{n}</a>' if link else f'<strong>{n}</strong>'
    al = aliases_of(d)
    if al:
        cell += f' <span class="aka">也叫 {esc("、".join(al))}</span>'
    return cell


def how_cell(d):
    return {'web': 'BootBridge 网页', 'ttl': 'TTL 串口', 'trial': '只能 RAM 试跑'}[route_of(d)]


def verified_table(devices):
    rows = [([name_cell(d), how_cell(d), inline(d.get('brief', ''))], f' data-k="{esc(keys_of(d))}"')
            for d in devices if route_of(d) != 'trial']
    return table(['机型', '安装方式', '说明'], rows, 'devs', {1: 'how'})


def device_list(devices, others):
    ok = [d for d in devices if route_of(d) != 'trial']
    trial = [d for d in devices if route_of(d) == 'trial']
    planned = [m for m in others if m['status'] == 'planned']
    wontdo = [m for m in others if m['status'] == 'wontdo']

    def other_name(m):  # aliases of these are for the filter only
        return esc(m['name'])

    out = []
    out.append(f'<section data-group><h2 id="ok"><span class="dot"></span>可以装 <span class="n">{len(ok)}</span></h2>')
    out.append('<p>点机型名进入它的安装步骤。</p>')
    out.append(verified_table(devices) + '</section>')

    out.append(f'<section data-group><h2 id="untested"><span class="dot untested"></span>有构建，未验证 <span class="n">{len(trial)}</span></h2>')
    out.append(text_block('还没有人在真机上跑过。只给能接 TTL 的人做 [RAM 试跑](/install/ram-trial)，不要写进闪存。'))
    out.append(table(['机型', '说明'], [([name_cell(d), inline(d.get('brief', ''))], f' data-k="{esc(keys_of(d))}"')
                                       for d in trial], 'devs') + '</section>')

    out.append(f'<section data-group><h2 id="planned"><span class="dot planned"></span>规划中 <span class="n">{len(planned)}</span></h2>')
    out.append(text_block('还没有构建，请不要刷。打算以后支持，下面写了现在卡在哪里。手里有这些机器、能接 TTL 的，'
                          '欢迎[参与收录](/contribute/)。'))
    out.append(table(['机型', '已知情况', '还缺什么'],
                     [([other_name(m), inline(m.get('known', '')), inline(m['missing'])],
                       f' id="{esc(anchor_of(m))}" data-k="{esc(keys_of(m))}"')
                      for m in planned], 'devs others') + '</section>')

    if wontdo:
        out.append(f'<section data-group><h2 id="wontdo"><span class="dot wontdo"></span>不打算做 <span class="n">{len(wontdo)}</span></h2>')
        out.append(table(['机型', '原因'], [([other_name(m), inline(m['reason'])],
                                           f' id="{esc(anchor_of(m))}" data-k="{esc(keys_of(m))}"')
                                          for m in wontdo], 'devs') + '</section>')
    out.append('<p id="none" hidden>没有匹配的机型。可能还没收录，换个写法试试（只输型号，不带品牌）。</p>')
    return '\n'.join(out)


def device_filter():
    return ('<p class="filter" hidden><label for="q">按型号筛选</label>'
            '<input id="q" type="search" placeholder="输入型号，例如 VS010、AX6000" autocomplete="off"></p>')


def home_others(devices, others):
    """Front page: every model that cannot be installed yet, each name a link to its entry."""
    trial = [d for d in devices if route_of(d) == 'trial']
    planned = [m for m in others if m['status'] == 'planned']
    wontdo = [m for m in others if m['status'] == 'wontdo']

    def names(models):
        return ('<ul class="names">' + ''.join(
            f'<li><a href="/devices/#{esc(anchor_of(m))}">{esc(m["name"])}</a></li>' for m in models) + '</ul>')

    out = []
    if trial:
        out.append(f'<h3><span class="dot untested"></span>有构建，未验证 <span class="n">{len(trial)}</span></h3>')
        out.append(text_block('U-Boot 已经编出来了，还没有人在真机上跑过。能接 TTL 的可以做 [RAM 试跑](/install/ram-trial)，'
                              '不要写进闪存。'))
        out.append(table(['机型', '说明'], [([name_cell(d), inline(d.get('brief', ''))], '') for d in trial], 'devs'))
    if planned:
        out.append(f'<h3><span class="dot planned"></span>规划中 <span class="n">{len(planned)}</span></h3>')
        out.append(text_block('还没有构建，请不要刷。点机型名看它现在的已知情况和还缺什么；'
                              '手里有这些机器的，欢迎[参与收录](/contribute/)。'))
        out.append(names(planned))
    if wontdo:
        out.append(f'<h3><span class="dot wontdo"></span>不打算做 <span class="n">{len(wontdo)}</span></h3>')
        out.append(text_block('这几款不在计划里，点机型名看原因。'))
        out.append(names(wontdo))
    return '\n'.join(out)


def home_finder():
    """On the front page: a plain form that opens the model list with ?q= filled in."""
    return ('<form class="finder" action="/devices/" method="get" role="search">'
            '<label for="hq">先找你的机型</label>'
            '<div><input id="hq" name="q" type="search" autocomplete="off" '
            'placeholder="路由器底部铭牌上的型号，例如 CR8806、VS010、RT3000">'
            '<button type="submit">查找</button></div></form>')


def oem_table(devices):
    rows = []
    for d in devices:
        if d['install']['method'] != 'bootbridge':
            continue
        hw = next((h['value'] for h in d.get('hardware') or [] if h['label'] == '硬件组'), '')
        rows.append(([name_cell(d), f'<code>{esc(d["install"]["oem_firmware"])}</code>', inline(hw)], ''))
    return table(['机型（铭牌）', '需要的原厂版本', '硬件组'], rows, 'devs')


def rescue_table(devices):
    rows = [([f'<a href="/devices/{d["id"]}">{esc(full_name(d))}</a>', inline(d['rescue']['how']),
              f'<code>{esc(d["rescue"].get("address", "192.168.1.1"))}</code>'], '')
            for d in devices if d.get('rescue') and route_of(d) != 'trial']
    return table(['机型', '怎么进入', '地址'], rows, 'devs')


def shell_table(devices):
    rows = [([f'<a href="/devices/{d["id"]}#shell">{esc(full_name(d))}</a>', DEVICE_STATUS[d['status']],
              inline(d.get('shell', {}).get('access') or '还不知道')], '')
            for d in devices if d['install']['method'] == 'ttl']
    return table(['机型', 'U-Boot', '拿 root 的线索'], rows, 'devs')


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
                out += [f'<details markdown="1"><summary>{esc(title or "详细")}</summary>', '']
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
            out.append(f'<p class="g">{esc(title)}</p>')
        out.append('<ul>')
        for href, text in items:
            cls = ' class="on"' if target_of(href)[0] == here else ''
            out.append(f'<li><a href="{href}"{cls}>{esc(text)}</a></li>')
        out.append('</ul>')
    out.append(f'<p class="contact">QQ 群 {QQ}<br><a href="{LINKS["issues"]}">GitHub Issues</a><br>'
               f'<a href="{LINKS["sponsor"]}">爱发电</a></p>')
    return '\n'.join(out)


def page_toc(body):
    """The page's own <h2> headings, for the right-hand column."""
    heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body, re.S)
    if len(heads) < 2:
        return ''

    def clean(h):
        return re.sub(r'<[^>]+>', '', re.sub(r'<span class="n">.*?</span>', '', h)).strip()

    items = ''.join(f'<li><a href="#{i}">{clean(h)}</a></li>' for i, h in heads)
    return f'<aside class="toc" aria-label="本页内容"><p>本页</p><ul>{items}</ul></aside>'


def layout(page, title, body, description='', full_title=None):
    desc = f'\n<meta name="description" content="{esc(description)}">' if description else ''
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title or f"{title} - {NAME}")}</title>{desc}
<link rel="icon" href="/logo.svg" type="image/svg+xml">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<input type="checkbox" id="nav-open" class="nav-open" aria-label="打开目录">
<header class="top">
<a class="brand" href="/"><img src="/logo.svg" alt="" width="26" height="26">{NAME}<small>安装指南</small></a>
<a class="ext" href="{LINKS["repo"]}">GitHub</a>
<label class="menu" for="nav-open">目录</label>
</header>
<div class="shell">
<nav class="side" aria-label="目录">
{side_nav(page)}
</nav>
<main class="doc">
{body}
<footer class="foot">U-Boot 遵循 GPL-2.0。本项目与各路由器厂商无关。</footer>
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


def fix_links(page, text):
    def internal(m):
        attr, href = m.group(1), m.group(2)
        path, rest = target_of(href)
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


def redirect_page(page, to):
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={to}">
<link rel="canonical" href="{to}">
<title>页面已移动 - {NAME}</title>
</head>
<body>
<p>页面已移动到 <a href="{to}">这里</a>。</p>
</body>
</html>
'''


def build(out):
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
    }

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE / 'static', out)
    pages = {}

    for src in sorted((SITE / 'pages').rglob('*.md')):
        page = src.relative_to(SITE / 'pages').with_suffix('.html').as_posix()
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
        desc = f'{full_name(d)} 安装本项目 U-Boot 的步骤、下载和验证情况。'
        pages[page] = layout(page, full_name(d), device_page(d, releases), desc)

    pages['404.html'] = layout('404.html', '页面不存在', '<h1>页面不存在</h1>\n'
                               '<p>链接可能已经变了。可以从<a href="/">首页</a>或<a href="/devices/">机型列表</a>重新找。</p>')

    for page, text in pages.items():
        f = out / page
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(fix_links(page, text), encoding='utf-8')

    for page, to in REDIRECTS.items():
        if page in pages:
            raise BuildError(f'redirect {page} would overwrite a page')
        path, rest = target_of(to)
        f = out / page
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(redirect_page(page, rel(page, path) + rest), encoding='utf-8')

    errors = check_links(out)
    if errors:
        raise BuildError('\n'.join(errors))
    return len(pages) + len(REDIRECTS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', type=Path, default=SITE / 'dist', help='output directory (default: site/dist)')
    args = ap.parse_args()
    try:
        n = build(args.out.resolve())
    except BuildError as e:
        print(f'build failed:\n{e}', file=sys.stderr)
        return 1
    print(f'{n} pages -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
