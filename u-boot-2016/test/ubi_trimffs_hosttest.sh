#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
cc -std=c11 -Wall -Wextra -Werror -I include test/ubi_trimffs_hosttest.c -o "$tmp"
"$tmp"
