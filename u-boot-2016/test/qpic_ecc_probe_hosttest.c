// SPDX-License-Identifier: GPL-2.0+
/*
 * Host test for lib/qpic_ecc_probe.c.
 *
 * Synthetic mode (no arguments): a fake flash where every programmed page
 * remembers the BCH strength it was written with; reading it in the other
 * format is an uncorrectable ECC error, erased pages read back as 0xff in
 * every format (as on QPIC).
 *
 * Image mode: qpic_ecc_probe_hosttest IMAGE TRUE_BITS MAX_BITS SPARE
 * IMAGE is a 2048-byte/page dump whose pages were written with TRUE_BITS.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <qpic_ecc_probe.h>

#define PAGE	2048U
#define BLOCK	0x20000ULL
#define CHIP	0x8000000ULL
#define NPAGES	(CHIP / PAGE)

static unsigned char *flash;	/* data */
static unsigned char *fmt;	/* 0 = erased, else 4/8 */
static unsigned int cur;	/* current controller format */
static int fail_set8, fail_read_at = -1, set8_calls;
static unsigned char page_buf[PAGE];
static int failures;

#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d %s\n", __func__, __LINE__, #c); failures++; } } while (0)

static int set_format(void *ctx, unsigned int bits)
{
	(void)ctx;
	if (bits == 8U) {
		set8_calls++;
		if (fail_set8)
			return -1;
	}
	cur = bits;
	return 0;
}

static int read_page(void *ctx, unsigned long long off, unsigned char *buf,
		     unsigned int len)
{
	unsigned long long pg = off / PAGE;

	(void)ctx;
	if (fail_read_at >= 0 && pg == (unsigned long long)fail_read_at)
		return -5;
	if (pg >= NPAGES || len != PAGE)
		return -22;
	if (!fmt[pg]) {
		memset(buf, 0xff, len);
		return QPIC_ECC_PROBE_READ_OK;
	}
	if (fmt[pg] != cur)
		return QPIC_ECC_PROBE_READ_ECC;
	memcpy(buf, flash + pg * PAGE, len);
	return QPIC_ECC_PROBE_READ_OK;
}

static void reset(void)
{
	memset(flash, 0xff, CHIP);
	memset(fmt, 0, NPAGES);
	cur = 0; fail_set8 = 0; fail_read_at = -1; set8_calls = 0;
}

static void prog(unsigned long long off, const void *data, unsigned int n,
		 unsigned int bits)
{
	memcpy(flash + off, data, n);
	fmt[off / PAGE] = bits;
}

static void put32(unsigned char *p, unsigned int v)
{
	p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24;
}

/* A QCA-style boot chain: SBL1, MIBIB at mibib_blk, APPSBL copies. */
static void boot_chain(unsigned int bits_sbl, unsigned int bits_rest,
		       unsigned int mibib_blk, unsigned int ptab_count)
{
	static const unsigned char sbl1[8] = { 0xd1, 0xdc, 0x4b, 0x84, 0x34, 0x10, 0xd7, 0x73 };
	static const unsigned char mib[8] = { 0xac, 0x9f, 0x56, 0xfe, 0x7a, 0x12, 0x7f, 0xcd };
	static const unsigned char ptab[8] = { 0xaa, 0x73, 0xee, 0x55, 0xdb, 0xbd, 0x5e, 0xe3 };
	static const struct { const char *name; unsigned int blk; } parts[] = {
		{ "0:SBL1", 0 }, { "0:MIBIB", 4 }, { "0:APPSBL", 40 },
		{ "0:APPSBL_1", 50 }, { "0:APPSBLX", 60 }, { "rootfs", 72 },
	};
	unsigned char p[PAGE];
	unsigned int i;

	memset(p, 0, sizeof(p));
	memcpy(p, sbl1, 8);
	prog(0, p, PAGE, bits_sbl);
	memset(p, 0, sizeof(p));
	memcpy(p, mib, 8);
	prog(mibib_blk * BLOCK, p, PAGE, bits_rest);
	memset(p, 0, sizeof(p));
	memcpy(p, ptab, 8);
	put32(p + 12, ptab_count);
	for (i = 0; i < sizeof(parts) / sizeof(parts[0]); i++) {
		unsigned char *e = p + 16 + i * 28;

		strncpy((char *)e, parts[i].name, 16);
		put32(e + 16, parts[i].blk);
		put32(e + 20, 8);
	}
	prog(mibib_blk * BLOCK + PAGE, p, PAGE, bits_rest);
	memset(p, 0, sizeof(p));
	memcpy(p, "\x7f" "ELF", 4);
	prog(40 * BLOCK, p, PAGE, bits_rest);
	prog(50 * BLOCK, p, PAGE, bits_rest);
	prog(60 * BLOCK, p, PAGE, bits_rest);	/* "0:APPSBLX" must not count */
}

static int run(unsigned int max_bits, unsigned int spare,
	       struct qpic_ecc_probe_result *res)
{
	struct qpic_ecc_probe_ops ops = {
		.ctx = NULL, .set_format = set_format, .read_page = read_page,
		.buf = page_buf, .block_size = BLOCK, .chip_size = CHIP,
	};
	return qpic_ecc_probe_run(&ops, max_bits, spare, res);
}

static void t_ecc8_board(void)
{
	struct qpic_ecc_probe_result r;

	reset(); boot_chain(8, 8, 4, 6);
	CHECK(run(8, 128, &r) == 0);
	CHECK(r.state == QPIC_ECC_PROBE_FOUND && r.bits == 8);
	CHECK(r.valid8 == 5 && r.valid4 == 0);
	CHECK(cur == 8);
}

static void t_ecc4_on_spare128(void)
{
	struct qpic_ecc_probe_result r;

	reset(); boot_chain(4, 4, 4, 6);
	CHECK(run(8, 128, &r) == 0);
	CHECK(r.state == QPIC_ECC_PROBE_FOUND && r.bits == 4 && r.valid4 == 5);
	CHECK(cur == 4);
}

static void t_spare64_never_tries_ecc8(void)
{
	struct qpic_ecc_probe_result r;

	reset(); boot_chain(4, 4, 4, 6);
	CHECK(run(4, 64, &r) == 0);
	CHECK(r.bits == 4 && r.state == QPIC_ECC_PROBE_FOUND && set8_calls == 0);
}

static void t_blank(void)
{
	struct qpic_ecc_probe_result r;

	reset();
	CHECK(run(8, 128, &r) == 0);
	CHECK(r.state == QPIC_ECC_PROBE_BLANK && r.bits == 8 && cur == 8);
	reset();
	CHECK(run(4, 64, &r) == 0);
	CHECK(r.state == QPIC_ECC_PROBE_BLANK && r.bits == 4 && cur == 4);
}

static void t_conflict(void)
{
	struct qpic_ecc_probe_result r;

	reset(); boot_chain(4, 8, 4, 6);
	CHECK(run(8, 128, &r) != 0);
	CHECK(r.state == QPIC_ECC_PROBE_CONFLICT && r.bits == 8);
	CHECK(r.valid4 == 1 && r.valid8 == 4);
}

static void t_weak(void)
{
	struct qpic_ecc_probe_result r;
	unsigned char p[PAGE];

	reset();
	memset(p, 0, sizeof(p));
	memcpy(p, "\xd1\xdc\x4b\x84\x34\x10\xd7\x73", 8);
	prog(0, p, PAGE, 4);
	CHECK(run(8, 128, &r) == 0);
	CHECK(r.state == QPIC_ECC_PROBE_WEAK && r.bits == 4);
}

static void t_mibib_elsewhere(void)
{
	struct qpic_ecc_probe_result r;

	reset(); boot_chain(8, 8, 7, 6);
	CHECK(run(8, 128, &r) == 0 && r.bits == 8 && r.valid8 == 5);
}

static void t_bad_ptab_count(void)
{
	struct qpic_ecc_probe_result r;

	reset(); boot_chain(8, 8, 4, 0x7fffffff);
	CHECK(run(8, 128, &r) == 0 && r.bits == 8 && r.valid8 == 3);
}

static void t_controller_refuses_ecc8(void)
{
	struct qpic_ecc_probe_result r;

	reset(); boot_chain(4, 4, 4, 6); fail_set8 = 1;
	CHECK(run(8, 128, &r) == 0 && r.bits == 4 && r.valid8 == 0);
}

static void t_read_error(void)
{
	struct qpic_ecc_probe_result r;

	reset(); boot_chain(8, 8, 4, 6); fail_read_at = 0;
	CHECK(run(8, 128, &r) != 0 && r.state == QPIC_ECC_PROBE_IOERR);
	CHECK(r.bits == 8 && cur == 8);
}

static int image_mode(const char *path, unsigned int truth,
		      unsigned int max_bits, unsigned int spare)
{
	struct qpic_ecc_probe_result r;
	FILE *f = fopen(path, "rb");
	unsigned long long pg, n;
	int ret;

	if (!f) { perror(path); return 2; }
	reset();
	n = fread(flash, 1, CHIP, f);
	fclose(f);
	for (pg = 0; pg < n / PAGE; pg++) {
		unsigned int i;

		for (i = 0; i < PAGE; i++)
			if (flash[pg * PAGE + i] != 0xff)
				break;
		fmt[pg] = i == PAGE ? 0 : truth;
	}
	ret = run(max_bits, spare, &r);
	printf("%s: ret %d state %s bits %u (ECC4 pages %u, ECC8 pages %u)\n",
	       path, ret, qpic_ecc_probe_state_name(r.state), r.bits,
	       r.valid4, r.valid8);
	return !(ret == 0 && r.bits == truth && r.state == QPIC_ECC_PROBE_FOUND);
}

int main(int argc, char **argv)
{
	flash = malloc(CHIP);
	fmt = malloc(NPAGES);
	if (!flash || !fmt)
		return 2;
	if (argc == 5)
		return image_mode(argv[1], atoi(argv[2]), atoi(argv[3]), atoi(argv[4]));
	t_ecc8_board();
	t_ecc4_on_spare128();
	t_spare64_never_tries_ecc8();
	t_blank();
	t_conflict();
	t_weak();
	t_mibib_elsewhere();
	t_bad_ptab_count();
	t_controller_refuses_ecc8();
	t_read_error();
	CHECK(qpic_ecc_probe_fallback(128) == 8 && qpic_ecc_probe_fallback(64) == 4);
	printf(failures ? "qpic_ecc_probe: %d FAILED\n" : "qpic_ecc_probe: all passed%.0d\n", failures);
	return !!failures;
}
