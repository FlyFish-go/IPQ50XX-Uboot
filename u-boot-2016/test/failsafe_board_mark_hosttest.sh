#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
cc -std=c11 -Wall -Wextra -Werror -I include test/failsafe_board_mark_hosttest.c -o "$tmp"
"$tmp"
