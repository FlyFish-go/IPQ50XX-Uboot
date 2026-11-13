/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * Parser for the Xiaomi official firmware container ("HDR1", .bin).
 *
 *   header (0x38 bytes): magic "HDR1", u32 sign offset, u32 JAMCRC, u16 type,
 *                        s16 model, u32 section offsets[10] (0 = unused)
 *   section: 48-byte header (u16 0xbabe, u16 0, u32 addr, u32 size, s16 mtd,
 *            s16 0, char name[32]) followed by size bytes of data
 *   then a signature block at the sign offset, up to the end of the file.
 *
 * The JAMCRC is ~crc32 of everything after the first 12 bytes. All integers
 * are little endian. The RSA signature is not checked: the stock OTA tool
 * does that, and the rescue page only needs to know what the file holds.
 *
 * Only a package whose sections are exactly "root.ubi" (plus the optional
 * "xiaoqiang_version") is accepted; anything that would write a loader, TZ
 * or other partition is refused. Pure logic: the caller supplies the crc.
 */
#ifndef XQIMAGE_H
#define XQIMAGE_H

#ifdef __UBOOT__
#include <common.h>
#else
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#endif

#define XQ_MAGIC	0x31524448u	/* "HDR1" */
#define XQ_HDR_SIZE	0x38
#define XQ_NSECT	10
#define XQ_SECT_HDR	48
#define XQ_SECT_MAGIC	0xbabeu

#define XQ_OK		0
#define XQ_EMAGIC	(-1)	/* not an HDR1 file */
#define XQ_EFORMAT	(-2)	/* truncated or inconsistent header/sections */
#define XQ_ECRC		(-3)
#define XQ_ESECTION	(-4)	/* unknown section name */
#define XQ_ENOROOT	(-5)	/* no root.ubi, or more than one */
#define XQ_ETYPE	(-6)	/* not a plain firmware package */

struct xq_info {
	const uint8_t *root;	/* the root.ubi section data */
	size_t root_size;
	int model;
};

static inline uint32_t xq_le32(const uint8_t *p)
{
	return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static inline uint32_t xq_le16(const uint8_t *p)
{
	return p[0] | (uint32_t)p[1] << 8;
}

/* crc32 is zlib's crc32(0, buf, len). */
static inline int xq_parse(const uint8_t *buf, size_t len,
			   uint32_t (*crc32)(const uint8_t *, size_t),
			   struct xq_info *out)
{
	uint32_t sign, prev_end = XQ_HDR_SIZE, off;
	int i, have_root = 0;

	out->root = NULL;
	out->root_size = 0;
	if (len < XQ_HDR_SIZE || xq_le32(buf) != XQ_MAGIC)
		return XQ_EMAGIC;
	sign = xq_le32(buf + 4);
	if (sign < XQ_HDR_SIZE || sign > len)
		return XQ_EFORMAT;
	if (xq_le16(buf + 12) != 0)
		return XQ_ETYPE;
	out->model = (int16_t)xq_le16(buf + 14);
	/* sections are laid out one after the other, in table order */
	for (i = 0; i < XQ_NSECT; i++) {
		const uint8_t *s;
		uint32_t size;
		char name[33];

		off = xq_le32(buf + 16 + 4 * i);
		if (!off)
			continue;
		if (off < prev_end || off > sign || sign - off < XQ_SECT_HDR)
			return XQ_EFORMAT;
		s = buf + off;
		if (xq_le16(s) != XQ_SECT_MAGIC)
			return XQ_EFORMAT;
		size = xq_le32(s + 8);
		if (size > sign - off - XQ_SECT_HDR)
			return XQ_EFORMAT;
		prev_end = off + XQ_SECT_HDR + size;
		memcpy(name, s + 16, 32);
		name[32] = 0;
		if (!strcmp(name, "root.ubi")) {
			if (have_root)
				return XQ_ENOROOT;
			have_root = 1;
			out->root = s + XQ_SECT_HDR;
			out->root_size = size;
		} else if (strcmp(name, "xiaoqiang_version")) {
			return XQ_ESECTION;
		}
	}
	if (!have_root || !out->root_size)
		return XQ_ENOROOT;
	/* the crc is checked last so that a wrong kind of file is named as such */
	if (0xffffffffu - crc32(buf + 12, len - 12) != xq_le32(buf + 8))
		return XQ_ECRC;
	return XQ_OK;
}

#endif /* XQIMAGE_H */
