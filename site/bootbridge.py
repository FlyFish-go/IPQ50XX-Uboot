"""Small guide-site hook; all tool-specific generation lives in bootbridge2."""
from pathlib import Path
import subprocess
import sys

SITE = Path(__file__).resolve().parent
WEB = SITE.parent / 'tools' / 'bootbridge2' / 'web'


def build_bootbridge(out):
    subprocess.run([sys.executable, str(WEB / 'build_site.py'),
                    '--release-dir', str(WEB / 'release' / 'BB2-R5'),
                    '--config', str(SITE / 'data' / 'bootbridge.json'),
                    '--repo-url', 'https://github.com/FlyFish-go/IPQ50XX-Uboot',
                    '--build-label', 'NX30 家族直接安装 U-Boot v0.2.0',
                    '--out', str(out)], check=True)
