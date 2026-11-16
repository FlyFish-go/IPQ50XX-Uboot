// SPDX-License-Identifier: GPL-2.0-or-later
#include "payload.h"
#include "../../bootbridge2/runtime/sha256.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char version[49] = "unknown";

static uint32_t le32(const uint8_t *p)
{
	return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24;
}

static int trailer(FILE *f, long *size, uint32_t *count, uint32_t *table)
{
	uint8_t t[64];

	if (fseek(f, 0, SEEK_END) || (*size = ftell(f)) < 64 ||
	    fseek(f, *size - 64, SEEK_SET) || fread(t, 1, 64, f) != 64 ||
	    memcmp(t, IPQI_PKG_MAGIC, 8))
		return -1;
	*count = le32(t + 8);
	*table = le32(t + 12);
	memcpy(version, t + 16, 48);
	version[48] = 0;
	return *count > 256 || *table + (uint64_t)*count * 88 + 64 != (uint64_t)*size ? -1 : 0;
}

void ipqi_sha256(const void *data, size_t len, uint8_t out[32])
{
	struct bb_sha256 s;

	bb_sha256_init(&s);
	bb_sha256_update(&s, data, len);
	bb_sha256_final(&s, out);
}

const char *ipqi_pkg_version(void)
{
	FILE *f = fopen("/proc/self/exe", "rb");
	long size;
	uint32_t count, table;

	if (f) {
		trailer(f, &size, &count, &table);
		fclose(f);
	}
	return version;
}

uint8_t *ipqi_payload(const char *name, size_t *len, char *err, size_t errlen)
{
	FILE *f = fopen("/proc/self/exe", "rb");
	long size;
	uint32_t count, table;
	uint8_t e[88], *data = NULL, sum[32];

	snprintf(err, errlen, "安装包里没有这台机器的 U-Boot");
	if (!f)
		return NULL;
	if (trailer(f, &size, &count, &table)) {
		snprintf(err, errlen, "安装包结构损坏");
		goto out;
	}
	for (uint32_t i = 0; i < count; i++) {
		uint32_t off, n;

		if (fseek(f, table + i * 88, SEEK_SET) || fread(e, 1, 88, f) != 88)
			break;
		if (strncmp((char *)e, name, 48))
			continue;
		off = le32(e + 48);
		n = le32(e + 52);
		if ((uint64_t)off + n > table || !(data = malloc(n ? n : 1)) ||
		    fseek(f, off, SEEK_SET) || fread(data, 1, n, f) != n) {
			snprintf(err, errlen, "安装包里的 U-Boot 读不出来");
			free(data);
			data = NULL;
			break;
		}
		ipqi_sha256(data, n, sum);
		if (memcmp(sum, e + 56, 32)) {
			snprintf(err, errlen, "安装包里的 U-Boot 校验不对");
			free(data);
			data = NULL;
			break;
		}
		*len = n;
		err[0] = 0;
		break;
	}
out:
	fclose(f);
	return data;
}
