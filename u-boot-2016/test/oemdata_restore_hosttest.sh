#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
cc -std=c11 -Wall -Wextra -Werror -idirafter include test/oemdata_restore_hosttest.c -o "$tmp"
"$tmp"
