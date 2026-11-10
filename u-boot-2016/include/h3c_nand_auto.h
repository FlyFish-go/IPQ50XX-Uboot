/* SPDX-License-Identifier: GPL-2.0+ */
#ifndef __H3C_NAND_AUTO_H__
#define __H3C_NAND_AUTO_H__

/*
 * Run-time NAND profile selection for images built without a pinned
 * H3C_NAND_PROFILE_ID.  The decision logic (h3c_nand_auto_core.c) is pure C;
 * the QPIC/MTD glue is in h3c_nand_auto.c.
 *
 * Selection never guesses: a chip with exactly one catalog row that admits
 * exactly one boot-chain ECC mode is taken from the catalog.  Anything else
 * (several rows, or a row that admits ECC4 and ECC8) is decided by reading
 * a fixed set of boot-chain pages in every candidate format.  A format is
 * only evidenced by pages that decode without an uncorrectable error, are not
 * blank and carry the magic of the image that must be stored there.  If the
 * evidence is not unique the result is "unknown" and the caller must keep all
 * NAND writes rejected.
 */
#include <h3c_nand_catalog.h>

#define H3C_NAND_AUTO_MAX_CAND     4U
#define H3C_NAND_AUTO_PAGE_BYTES   2048U
/* Valid pages needed in one format (and none in the other) to select it. */
#define H3C_NAND_AUTO_MIN_EVIDENCE 2U

/* h3c_nand_auto_ops.read_page() results other than a hard error (< 0). */
#define H3C_NAND_AUTO_READ_OK      0
#define H3C_NAND_AUTO_READ_ECC     1	/* uncorrectable ECC error */

/* h3c_nand_auto_resolve() results. */
#define H3C_NAND_AUTO_OK            0
#define H3C_NAND_AUTO_E_NOROW      -1	/* chip not in the catalog */
#define H3C_NAND_AUTO_E_UNKNOWN    -2	/* evidence not unique / unusable */
#define H3C_NAND_AUTO_E_IO         -3	/* switching or reading failed */
#define H3C_NAND_AUTO_E_NEED_PROBE -4	/* ambiguous and no ops supplied */

enum h3c_nand_auto_kind {
	H3C_NAND_AUTO_KIND_SBL1 = 1,	/* QC SBL1 magic or ELF */
	H3C_NAND_AUTO_KIND_ELF,		/* ELF image (APPSBL) */
	H3C_NAND_AUTO_KIND_MIBIB_HDR,	/* MIBIB header page */
	H3C_NAND_AUTO_KIND_MIBIB_PTAB,	/* MIBIB partition table page */
};

struct h3c_nand_auto_page {
	unsigned long long offset;
	unsigned int kind;
};

struct h3c_nand_auto_cand {
	const struct h3c_nand_catalog_profile *row;
	unsigned int mode;	/* 4 or 8 */
	unsigned int spare;	/* raw spare bytes of this row's boot chain */
};

struct h3c_nand_auto_ops {
	void *ctx;
	/* Make the controller read with this boot-chain format; 0 on success. */
	int (*set_format)(void *ctx, unsigned int ecc_bits, unsigned int spare);
	/* Read one page into buf (buf_len bytes, owned by the caller of
	 * resolve). OK, READ_ECC, or a negative hard error. */
	int (*read_page)(void *ctx, unsigned long long offset,
			 unsigned char *buf, unsigned int len);
	unsigned char *buf;
	unsigned int buf_len;	/* at least H3C_NAND_AUTO_PAGE_BYTES */
};

struct h3c_nand_auto_result {
	const struct h3c_nand_catalog_profile *row;
	unsigned int mode;
	unsigned int spare;
	int probed;		/* 0: catalog only, 1: boot-chain evidence */
	unsigned int valid4, valid8;
};

/* Fixed boot-chain evidence pages (identical on all boards). */
extern const struct h3c_nand_auto_page h3c_nand_auto_pages[];
extern const unsigned int h3c_nand_auto_page_count;

/* 1 when the page content is not blank and carries the magic of kind. */
int h3c_nand_auto_page_valid(unsigned int kind, const unsigned char *page,
			     unsigned int len);

/* Candidates (row, mode) for a detected chip; *rows is the number of rows
 * that match id and model. Returns the candidate count. */
unsigned int h3c_nand_auto_collect(const unsigned char id[2], const char *model,
				   struct h3c_nand_auto_cand *out,
				   unsigned int max, unsigned int *rows);

/* Catalog-only decision: H3C_NAND_AUTO_OK with res filled when the chip has
 * exactly one row and that row admits exactly one boot-chain mode,
 * E_NEED_PROBE when a probe is required, otherwise E_NOROW/E_UNKNOWN. */
int h3c_nand_auto_resolve_catalog(const unsigned char id[2], const char *model,
				  struct h3c_nand_auto_result *res);

/* Full decision, probing the boot chain through ops when needed. On success
 * the controller is left in the selected format. */
int h3c_nand_auto_resolve(const unsigned char id[2], const char *model,
			  const struct h3c_nand_auto_ops *ops,
			  struct h3c_nand_auto_result *res);

#ifndef H3C_NAND_AUTO_HOST_TEST
/* ---- U-Boot glue (h3c_nand_auto.c, qpic_nand.c) ---- */
/* Forget any earlier decision; called when the QPIC reads the NAND ID. */
void h3c_nand_auto_reset(void);
/* QPIC ID time, catalog only. Returns 1 and fills row/mode when the chip
 * is decided without reading flash, 0 when a probe is pending or the chip
 * is unusable. */
int h3c_nand_auto_early(const unsigned char id[2], const char *model,
			const struct h3c_nand_catalog_profile **row,
			unsigned int *mode);
/* After NAND init: probe the boot chain if the decision is still pending. */
void h3c_nand_auto_run(void);
/* 1 only when a profile and boot-chain ECC mode have been selected. */
int h3c_nand_auto_ok(void);
const struct h3c_nand_catalog_profile *h3c_nand_auto_row(void);
unsigned int h3c_nand_auto_mode(void);
/* qpic_nand.c: switch the controller to a boot-chain format / record it. */
int qpic_nand_auto_set_format(unsigned int bits, unsigned int spare);
void qpic_nand_auto_set_load_bits(unsigned int bits);
#endif

#endif /* __H3C_NAND_AUTO_H__ */
