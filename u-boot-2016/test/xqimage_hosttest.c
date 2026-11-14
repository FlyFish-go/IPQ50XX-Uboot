/* Host test for include/xqimage.h with synthetic packages, and optionally a
 * real official ROM given as argv[1] (it is not part of the repository). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <xqimage.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)

static uint32_t crc32z(const uint8_t *p, size_t n)
{
	uint32_t c = 0xffffffffu;
	size_t i; int k;
	for (i = 0; i < n; i++) {
		c ^= p[i];
		for (k = 0; k < 8; k++)
			c = c & 1 ? c >> 1 ^ 0xedb88320u : c >> 1;
	}
	return ~c;
}

static void w16(uint8_t *p, uint32_t v) { p[0] = v; p[1] = v >> 8; }
static void w32(uint8_t *p, uint32_t v) { w16(p, v); w16(p + 2, v >> 16); }

struct sec { const char *name; uint32_t size; };

/* Build a package: header, sections in table order, 272-byte signature block. */
static size_t build(uint8_t *b, int type, const struct sec *s, int n, int fix_crc)
{
	size_t pos = XQ_HDR_SIZE;
	int i;
	uint32_t j;

	memset(b, 0, 4096);
	w32(b, XQ_MAGIC);
	w16(b + 12, type);
	w16(b + 14, 51);
	for (i = 0; i < n; i++) {
		w32(b + 16 + 4 * i, pos);
		w16(b + pos, XQ_SECT_MAGIC);
		w32(b + pos + 4, 0xffffffffu);
		w32(b + pos + 8, s[i].size);
		w16(b + pos + 12, 0xffff);
		strncpy((char *)b + pos + 16, s[i].name, 31);
		for (j = 0; j < s[i].size; j++)
			b[pos + XQ_SECT_HDR + j] = (uint8_t)(j * 7 + i);
		pos += XQ_SECT_HDR + s[i].size;
		pos = (pos + 3) & ~3u;
	}
	w32(b + 4, pos);
	memset(b + pos, 0xff, 272);
	pos += 272;
	if (fix_crc)
		w32(b + 8, 0xffffffffu - crc32z(b + 12, pos - 12));
	return pos;
}

int main(int argc, char **argv)
{
	static uint8_t b[4096];
	struct xq_info in;
	size_t len, i;
	static const struct sec good[] = { { "xiaoqiang_version", 0x69 }, { "root.ubi", 0x500 } };
	static const struct sec only_root[] = { { "root.ubi", 0x200 } };
	static const struct sec evil[] = { { "root.ubi", 0x200 }, { "uboot.bin", 0x100 } };
	static const struct sec evil2[] = { { "uboot.bin", 0x100 }, { "root.ubi", 0x200 } };
	static const struct sec twice[] = { { "root.ubi", 0x100 }, { "root.ubi", 0x100 } };
	static const struct sec none[] = { { "xiaoqiang_version", 0x40 } };
	static const struct sec empty[] = { { "root.ubi", 0 } };
	static const struct sec prefix[] = { { "root.ubi2", 0x100 } };

	len = build(b, 0, good, 2, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_OK);
	CHECK(in.root_size == 0x500 && in.model == 51);
	CHECK(in.root == b + XQ_HDR_SIZE + XQ_SECT_HDR + 0x6c + XQ_SECT_HDR);	/* 0x69 padded to 0x6c */
	CHECK(in.root[1] == 8);							/* section index 1, j=1 */
	len = build(b, 0, only_root, 1, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_OK && in.root_size == 0x200);

	/* unknown sections are refused wherever they are */
	len = build(b, 0, evil, 2, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_ESECTION);
	len = build(b, 0, evil2, 2, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_ESECTION);
	len = build(b, 0, prefix, 1, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_ESECTION);
	len = build(b, 0, twice, 2, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_ENOROOT);
	len = build(b, 0, none, 1, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_ENOROOT);
	len = build(b, 0, empty, 1, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_ENOROOT);
	/* ssh/env packages (type != 0) are not firmware */
	len = build(b, 12, good, 2, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_ETYPE);

	/* crc */
	len = build(b, 0, good, 2, 0);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_ECRC);
	len = build(b, 0, good, 2, 1);
	b[len - 20] ^= 1;
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_ECRC);
	/* not HDR1 */
	CHECK(xq_parse((const uint8_t *)"\x23\x49\x42\x55 and more bytes of a ubi image 0123456789abcdef0123456789abcdef", 64,
		       crc32z, &in) == XQ_EMAGIC);
	CHECK(xq_parse(b, 3, crc32z, &in) == XQ_EMAGIC);

	/* truncation at every length is refused and never reads past len */
	len = build(b, 0, good, 2, 1);
	for (i = 0; i < len; i++) {
		uint8_t *c = malloc(i ? i : 1);
		memcpy(c, b, i);
		CHECK(xq_parse(c, i, crc32z, &in) != XQ_OK);
		free(c);
	}
	/* a section claiming more than the file holds */
	len = build(b, 0, good, 2, 1);
	w32(b + XQ_HDR_SIZE + 8, 0x7fffffffu);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_EFORMAT);
	len = build(b, 0, good, 2, 1);
	w32(b + XQ_HDR_SIZE + 8, 0xffffffffu);			/* offset + size wraps */
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_EFORMAT);
	/* offsets going backwards or into the header */
	len = build(b, 0, good, 2, 1);
	w32(b + 20, XQ_HDR_SIZE);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_EFORMAT);
	len = build(b, 0, good, 2, 1);
	w32(b + 16, 8);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_EFORMAT);
	/* bad section magic */
	len = build(b, 0, good, 2, 1);
	b[XQ_HDR_SIZE] = 0;
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_EFORMAT);
	/* sign offset beyond the file */
	len = build(b, 0, good, 2, 1);
	w32(b + 4, len + 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_EFORMAT);

	/* model id allowlist: the test packages carry model 51 (CR8806) */
	len = build(b, 0, good, 2, 1);
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_OK);
	CHECK(xq_check_model(in.model, 51) == XQ_OK);
	CHECK(xq_check_model(in.model, 0) == XQ_OK);
	CHECK(xq_check_model(44, 51) == XQ_EMODEL);		/* RA81 */
	CHECK(xq_check_model(-1, 51) == XQ_EMODEL);
	w16(b + 14, 44);
	w32(b + 8, 0xffffffffu - crc32z(b + 12, len - 12));
	CHECK(xq_parse(b, len, crc32z, &in) == XQ_OK && in.model == 44);
	CHECK(xq_check_model(in.model, 51) == XQ_EMODEL);

	if (argc > 1) {
		FILE *fp = fopen(argv[1], "rb");
		uint8_t *d;
		long n;
		CHECK(fp);
		fseek(fp, 0, SEEK_END); n = ftell(fp); fseek(fp, 0, SEEK_SET);
		d = malloc(n);
		CHECK(d && fread(d, 1, n, fp) == (size_t)n);
		fclose(fp);
		CHECK(xq_parse(d, n, crc32z, &in) == XQ_OK);
		CHECK(in.root_size > 0x100000 && in.root_size < 0x2400000);
		CHECK(memcmp(in.root, "UBI#", 4) == 0);
		printf("real ROM: model %d, root.ubi %zu bytes at offset 0x%zx\n", in.model,
		       in.root_size, (size_t)(in.root - d));
		d[n / 2] ^= 0x40;
		CHECK(xq_parse(d, n, crc32z, &in) == XQ_ECRC);
		free(d);
	}
	puts("XQIMAGE_HOSTTEST_PASS");
	return 0;
}
