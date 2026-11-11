#!/bin/sh
# qpic_ecc_probe_hosttest.sh - boot-chain ECC detection (pure core).
# Extra arguments are passed to image mode: IMAGE TRUE_BITS MAX_BITS SPARE.
set -eu
cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -DQPIC_ECC_PROBE_HOST_TEST \
  -Iinclude -idirafter include test/qpic_ecc_probe_hosttest.c \
  lib/qpic_ecc_probe.c -o "$tmp/probe"
"$tmp/probe" "$@"
