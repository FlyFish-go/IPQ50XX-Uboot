"""Small guide-site hook; all tool-specific generation lives in bootbridge2."""
from pathlib import Path
import subprocess
import sys
import tempfile

SITE = Path(__file__).resolve().parent
WEB = SITE.parent / 'tools' / 'bootbridge2' / 'web'


def build_bootbridge(out, layout, fix_links):
    # Use the same frame as every guide page. The web builder inserts its own
    # body/assets before calculating SHA256SUMS (also for the standalone ZIP).
    page = 'bootbridge/index.html'
    shell = layout(page, 'BootBridge', '__BOOTBRIDGE_BODY__',
                   '在浏览器本地用 H3C 官方固件生成 BootBridge 桥接包，不上传文件。')
    shell = shell.replace('</head>', '__BOOTBRIDGE_HEAD__\n</head>')
    with tempfile.TemporaryDirectory(prefix='bootbridge-frame-') as tmp:
        frame = Path(tmp) / 'frame.html'
        frame.write_text(fix_links(page, shell), encoding='utf-8')
        subprocess.run([sys.executable, str(WEB / 'build_site.py'),
                        '--release-dir', str(WEB / 'release' / 'BB2-R5'),
                        '--config', str(SITE / 'data' / 'bootbridge.json'),
                        '--repo-url', 'https://github.com/FlyFish-go/IPQ50XX-Uboot',
                        '--build-label', 'NX30 家族直接安装 U-Boot v0.2.0',
                        '--guide-frame', str(frame),
                        '--out', str(out)], check=True)
