/* SPDX-License-Identifier: GPL-2.0+ */
#ifndef __QPIC_ECC_PROBE_H__
#define __QPIC_ECC_PROBE_H__

/*
 * Boot-chain ECC detection for QPIC serial NAND.
 *
 * The BCH strength a board uses is a vendor choice, not a property of the
 * chip: the same part is ECC4 on one board and ECC8 on another, and vendor
 * ID tables disagree. The flash itself is the only reliable record, so the
 * format is read back from it: SBL1, the MIBIB header and partition table
 * and both APPSBL copies are read in every format the chip can hold, and a
 * format is taken only when it yields valid pages and the other yields none.
 *
 * The decision logic is pure C; the controller is reached through ops so it
 * can be exercised on the host (test/qpic_ecc_probe_hosttest.sh).
 */

#define QPIC_ECC_PROBE_PAGE_BYTES	2048U
#define QPIC_ECC_PROBE_MIBIB_MAX_BLOCK	16U	/* MIBIB is searched in blocks 1..15 */
#define QPIC_ECC_PROBE_MIN_EVIDENCE	2U

/* read_page() results other than a hard error (< 0) */
#define QPIC_ECC_PROBE_READ_OK		0
#define QPIC_ECC_PROBE_READ_ECC		1	/* uncorrectable in this format */

enum qpic_ecc_probe_state {
	QPIC_ECC_PROBE_FOUND = 0,	/* >= MIN_EVIDENCE pages, none in the other format */
	QPIC_ECC_PROBE_WEAK,		/* one page only, none in the other format */
	QPIC_ECC_PROBE_BLANK,		/* no evidence at all: fallback format */
	QPIC_ECC_PROBE_CONFLICT,	/* evidence in both formats: fallback, no writes */
	QPIC_ECC_PROBE_IOERR,		/* reading or switching failed: fallback, no writes */
};

struct qpic_ecc_probe_ops {
	void *ctx;
	/* Configure the controller for 4- or 8-bit BCH; 0 on success. */
	int (*set_format)(void *ctx, unsigned int bits);
	/* Read len bytes of the page at offset: READ_OK, READ_ECC or < 0. */
	int (*read_page)(void *ctx, unsigned long long offset,
			 unsigned char *buf, unsigned int len);
	unsigned char *buf;		/* QPIC_ECC_PROBE_PAGE_BYTES, owned by the caller */
	unsigned long long block_size;	/* erase block size in bytes */
	unsigned long long chip_size;	/* device size in bytes */
};

struct qpic_ecc_probe_result {
	unsigned int bits;		/* selected (or fallback) BCH strength */
	unsigned int valid4, valid8;	/* evidence pages per format */
	int state;			/* enum qpic_ecc_probe_state */
};

/* Format used when the flash gives no answer: the rule of the QCA SBL1
 * SPI-NAND table (spare >= 128 bytes -> ECC8, else ECC4). */
unsigned int qpic_ecc_probe_fallback(unsigned int spare_bytes);

/* 1 when the page is not blank and starts with the magic of kind. */
int qpic_ecc_probe_page_valid(int kind, const unsigned char *page,
			      unsigned int len);

/*
 * Probe the boot chain. max_bits is 8 when the chip's spare area can hold
 * 8-bit BCH codewords (>= 80 bytes per 2 KiB page), else 4. On return the
 * controller is left in res->bits (when set_format succeeds).
 * Returns 0 when res->bits may be used for writes (FOUND, WEAK, BLANK).
 */
int qpic_ecc_probe_run(const struct qpic_ecc_probe_ops *ops,
		       unsigned int max_bits, unsigned int spare_bytes,
		       struct qpic_ecc_probe_result *res);

const char *qpic_ecc_probe_state_name(int state);

#endif /* __QPIC_ECC_PROBE_H__ */
