#!/usr/bin/env python3
"""Check that every writable production profile exposes firmware mode pages."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "failsafe/modules/misc.c").read_text(encoding="utf-8")
match = re.search(
    r"#if(?:def)?\s+(?P<guard>.*?)\n"
    r"\s*httpd_register_uri_handler\(inst, \"/firmware-dual\.html\".*?\n"
    r"\s*httpd_register_uri_handler\(inst, \"/firmware-single\.html\".*?\n"
    r"#endif",
    source,
    re.S,
)
assert match, "firmware mode route registration block not found"
guard = match.group("guard")
required = {
    "CONFIG_H3C_IPQ5018_COMMON",
}
missing = sorted(name for name in required if name not in guard)
assert not missing, "writable production profiles missing firmware mode routes: " + ", ".join(missing)

main = (ROOT / "failsafe/fsdata/main.js").read_text(encoding="utf-8")
assert "'/firmware-dual.html': 'firmware'" in main
assert "'/firmware-single.html': 'firmware'" in main
assert "'/firmware-dual.html'" in main
assert "'/firmware-single.html'" in main

print("PASS firmware mode URI registration covers A/B/C/D production profiles")
