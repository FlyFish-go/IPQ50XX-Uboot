#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Count preprocessor conditions in common code that name a board.

A new board should be a device tree, a defconfig and Kconfig selections.
Every "#if CONFIG_TARGET_IPQ5018_<board>" in shared code is a place the
next board has to be added by hand, so the number may only go down.

  board_conditionals.py            print the count per file
  board_conditionals.py --check    fail if the count exceeds the budget
  board_conditionals.py --update   lower the budget to the current count
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUDGET = Path(__file__).with_name("board-conditionals.budget")
DIRECTIVE = re.compile(r"^[ \t]*#[ \t]*(?:if|ifdef|ifndef|elif)\b(.*)$", re.M)
BOARD = re.compile(r"\bCONFIG_TARGET_IPQ5018_\w+")


def count():
    files = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", "u-boot-2016/*.[chS]"],
        check=True, capture_output=True).stdout.decode().split("\0")
    per_file = {}
    for name in files:
        if not name or "/test/" in name or "/board/ipq5018/" in name:
            continue
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            continue
        text = path.read_bytes().decode("latin-1")
        if "CONFIG_TARGET_IPQ5018_" not in text:
            continue
        text = re.sub(r"\\\n", " ", text)
        hits = sum(1 for m in DIRECTIVE.finditer(text) if BOARD.search(m.group(1)))
        if hits:
            per_file[name] = hits
    return per_file


def main():
    per_file = count()
    total = sum(per_file.values())
    if "--update" in sys.argv:
        BUDGET.write_text("%d\n" % total)
    budget = int(BUDGET.read_text()) if BUDGET.exists() else None
    if "--check" not in sys.argv:
        for name, hits in sorted(per_file.items(), key=lambda kv: (-kv[1], kv[0])):
            print("%4d  %s" % (hits, name))
    print("board conditionals: %d in %d files (budget %s)" % (total, len(per_file), budget))
    if "--check" in sys.argv and budget is not None and total > budget:
        print("FAIL: common code gained a per-board condition; use a capability "
              "symbol selected by the board instead.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
