#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Kernel version from FIT descriptions and legacy uImage names.
set -eu
cd "$(dirname "$0")/.."
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/t.c" <<'C'
#include <stdio.h>
#include <string.h>
#include <slot_probe.h>
static int n;
static void chk(const char *in, size_t len, int want_rc, const char *want)
{
	char out[33];
	int rc = slot_probe_kernel_version((const unsigned char *)in, len, out, sizeof(out));
	if (rc != want_rc || (rc == 0 && strcmp(out, want))) {
		printf("FAIL %s: rc %d out '%s'\n", want, rc, rc ? "" : out); n++;
	}
}
int main(void)
{
	static const char fit[] = "\xd0\x0d\xfe\xed....description\0ARM64 OpenWrt Linux-6.6.73\0kernel";
	static const char uimg[] = "\x27\x05\x19\x56xxxxxxxxxxxxxxxxxxxxxxxxxxxxARM OpenWrt Linux-4.4.60\0\0\0";
	chk(fit, sizeof(fit), 0, "6.6.73");
	chk(uimg, sizeof(uimg), 0, "4.4.60");
	chk("Linux-5.4.213-rt3\0", 18, 0, "5.4.213-rt3");
	chk("Linux-x Linux-5", 15, -2, "");          /* no "x.y" */
	chk("no version here", 15, -2, "");
	chk("Linux-6.1", 9, 0, "6.1");                /* ends at buffer end */
	chk("Linux-1234567890.1234567890123456789012345", 42, 0, "1234567890.123456789012345678901"); /* truncated to 32 chars */
	if (!n) puts("SLOT_PROBE_KVER_HOSTTEST_PASS");
	return n != 0;
}
C
cc -std=gnu99 -Wall -Wextra -Werror -DSLOT_PROBE_HOST_TEST -idirafter include \
   "$tmp/t.c" failsafe/modules/slot_probe_kver.c -o "$tmp/t" 2>&1 | head -20
"$tmp/t"
