#!/bin/sh
# Optional argument: a real Xiaomi official .bin (kept outside the repository).
set -eu
cd "$(dirname "$0")/.."
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all \
   -idirafter include test/xqimage_hosttest.c -o "$tmp"
"$tmp" "$@"
