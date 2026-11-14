// SPDX-License-Identifier: GPL-2.0
/* Kernel version from the start of a kernel volume; host tested. */
#ifdef SLOT_PROBE_HOST_TEST
#include <errno.h>
#include <stddef.h>
#include <string.h>
#else
#include <common.h>
#include <asm/errno.h>
#endif
#include <slot_probe.h>

static int kver_char(unsigned char c)
{
	return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') ||
	       (c >= 'A' && c <= 'Z') || c == '.' || c == '-' || c == '_' ||
	       c == '+';
}

int slot_probe_kernel_version(const unsigned char *buf, size_t len,
			      char *out, size_t out_len)
{
	static const char tag[] = "Linux-";
	const size_t tl = sizeof(tag) - 1;
	size_t i, n;

	if (!buf || !out || out_len < 2)
		return -ENOENT;
	out[0] = 0;
	for (i = 0; i + tl < len; i++) {
		if (memcmp(buf + i, tag, tl) || buf[i + tl] < '0' || buf[i + tl] > '9')
			continue;
		for (n = 0; i + tl + n < len && n + 1 < out_len &&
			    kver_char(buf[i + tl + n]); n++)
			out[n] = buf[i + tl + n];
		/* need at least "x.y" */
		if (n >= 3 && memchr(out, '.', n)) {
			out[n] = 0;
			return 0;
		}
		out[0] = 0;
	}
	return -ENOENT;
}
