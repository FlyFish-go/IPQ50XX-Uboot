// SPDX-License-Identifier: GPL-2.0+
/* Pure decision logic for run-time NAND profile selection. No U-Boot
 * headers are needed; the controller is reached through an ops struct so the
 * logic can be exercised on the host. */
#ifdef H3C_NAND_AUTO_HOST_TEST
#include <string.h>
#else
#include <common.h>
#endif
#include <h3c_nand_auto.h>

unsigned int h3c_nand_ecc_unique_mode(int valid4, int valid8);

/* OEM layout shared by all boards (see rt3000_b_layout.c boot_prefix). */
const struct h3c_nand_auto_page h3c_nand_auto_pages[] = {
	{ 0x00000000ULL, H3C_NAND_AUTO_KIND_SBL1 },	/* 0:SBL1 */
	{ 0x00080000ULL, H3C_NAND_AUTO_KIND_MIBIB_HDR },/* 0:MIBIB page 0 */
	{ 0x00080800ULL, H3C_NAND_AUTO_KIND_MIBIB_PTAB },/* 0:MIBIB page 1 */
	{ 0x00500000ULL, H3C_NAND_AUTO_KIND_ELF },	/* 0:APPSBL */
	{ 0x00640000ULL, H3C_NAND_AUTO_KIND_ELF },	/* 0:APPSBL_1 */
};
const unsigned int h3c_nand_auto_page_count =
	sizeof(h3c_nand_auto_pages) / sizeof(h3c_nand_auto_pages[0]);

static const unsigned char magic_elf[4] = { 0x7f, 'E', 'L', 'F' };
static const unsigned char magic_sbl1[8] = {
	0xd1, 0xdc, 0x4b, 0x84, 0x34, 0x10, 0xd7, 0x73 };
static const unsigned char magic_mibib[8] = {
	0xac, 0x9f, 0x56, 0xfe, 0x7a, 0x12, 0x7f, 0xcd };
static const unsigned char magic_ptab[8] = {
	0xaa, 0x73, 0xee, 0x55, 0xdb, 0xbd, 0x5e, 0xe3 };

int h3c_nand_auto_page_valid(unsigned int kind, const unsigned char *page,
			     unsigned int len)
{
	unsigned int i;

	if (!page || len < 8U)
		return 0;
	/* Erased pages decode cleanly in every format: never evidence. */
	for (i = 0; i < len; i++)
		if (page[i] != 0xffU)
			break;
	if (i == len)
		return 0;
	switch (kind) {
	case H3C_NAND_AUTO_KIND_SBL1:
		return !memcmp(page, magic_sbl1, sizeof(magic_sbl1)) ||
		       !memcmp(page, magic_elf, sizeof(magic_elf));
	case H3C_NAND_AUTO_KIND_ELF:
		return !memcmp(page, magic_elf, sizeof(magic_elf));
	case H3C_NAND_AUTO_KIND_MIBIB_HDR:
		return !memcmp(page, magic_mibib, sizeof(magic_mibib));
	case H3C_NAND_AUTO_KIND_MIBIB_PTAB:
		return !memcmp(page, magic_ptab, sizeof(magic_ptab));
	}
	return 0;
}

unsigned int h3c_nand_auto_collect(const unsigned char id[2], const char *model,
				   struct h3c_nand_auto_cand *out,
				   unsigned int max, unsigned int *rows)
{
	unsigned int i, n = 0, matched = 0;

	if (rows)
		*rows = 0;
	if (!id || !model || !out)
		return 0;
	for (i = 0; i < H3C_NAND_CATALOG_PROFILE_COUNT; i++) {
		const struct h3c_nand_catalog_profile *p =
			&h3c_nand_catalog_profiles[i];
		unsigned int bits;

		if (p->id[0] != id[0] || p->id[1] != id[1] ||
		    !p->qpic_model || strcmp(p->qpic_model, model))
			continue;
		matched++;
		for (bits = 4U; bits <= 8U; bits += 4U) {
			if (!(p->appsbl_ecc_mode_mask &
			      h3c_nand_catalog_mode_bit(bits)))
				continue;
			if (n < max) {
				out[n].row = p;
				out[n].mode = bits;
				out[n].spare = p->appsbl_raw_spare_bytes;
			}
			n++;
		}
	}
	if (rows)
		*rows = matched;
	return n;
}

static int h3c_nand_auto_finish(const struct h3c_nand_auto_cand *c, int probed,
				unsigned int v4, unsigned int v8,
				struct h3c_nand_auto_result *res)
{
	/* The row must also be qualified for run-time reads in that mode. */
	if (!(c->row->runtime_ecc_mode_mask &
	      h3c_nand_catalog_mode_bit(c->mode)))
		return H3C_NAND_AUTO_E_UNKNOWN;
	res->row = c->row;
	res->mode = c->mode;
	res->spare = c->spare;
	res->probed = probed;
	res->valid4 = v4;
	res->valid8 = v8;
	return H3C_NAND_AUTO_OK;
}

int h3c_nand_auto_resolve_catalog(const unsigned char id[2], const char *model,
				  struct h3c_nand_auto_result *res)
{
	struct h3c_nand_auto_cand c[H3C_NAND_AUTO_MAX_CAND];
	unsigned int rows, n;

	if (!res)
		return H3C_NAND_AUTO_E_UNKNOWN;
	memset(res, 0, sizeof(*res));
	n = h3c_nand_auto_collect(id, model, c, H3C_NAND_AUTO_MAX_CAND, &rows);
	if (!rows)
		return H3C_NAND_AUTO_E_NOROW;
	if (rows == 1U && n == 1U)
		return h3c_nand_auto_finish(&c[0], 0, 0, 0, res);
	if (n == 2U && c[0].mode != c[1].mode)
		return H3C_NAND_AUTO_E_NEED_PROBE;
	return H3C_NAND_AUTO_E_UNKNOWN;
}

/* Count valid evidence pages for one candidate. */
static int h3c_nand_auto_count(const struct h3c_nand_auto_ops *ops,
			       const struct h3c_nand_auto_cand *c,
			       unsigned int *valid)
{
	unsigned int i;

	*valid = 0;
	if (ops->set_format(ops->ctx, c->mode, c->spare))
		return H3C_NAND_AUTO_E_IO;
	for (i = 0; i < h3c_nand_auto_page_count; i++) {
		int ret = ops->read_page(ops->ctx, h3c_nand_auto_pages[i].offset,
					 ops->buf, H3C_NAND_AUTO_PAGE_BYTES);

		if (ret < 0)
			return H3C_NAND_AUTO_E_IO;
		if (ret != H3C_NAND_AUTO_READ_OK)
			continue;	/* uncorrectable: not evidence */
		if (h3c_nand_auto_page_valid(h3c_nand_auto_pages[i].kind,
					     ops->buf,
					     H3C_NAND_AUTO_PAGE_BYTES))
			(*valid)++;
	}
	return H3C_NAND_AUTO_OK;
}

int h3c_nand_auto_resolve(const unsigned char id[2], const char *model,
			  const struct h3c_nand_auto_ops *ops,
			  struct h3c_nand_auto_result *res)
{
	struct h3c_nand_auto_cand c[H3C_NAND_AUTO_MAX_CAND];
	const struct h3c_nand_auto_cand *c4 = NULL, *c8 = NULL;
	unsigned int rows, n, v4, v8, mode;
	int ret;

	ret = h3c_nand_auto_resolve_catalog(id, model, res);
	if (ret != H3C_NAND_AUTO_E_NEED_PROBE)
		return ret;
	if (!ops || !ops->set_format || !ops->read_page || !ops->buf ||
	    ops->buf_len < H3C_NAND_AUTO_PAGE_BYTES)
		return H3C_NAND_AUTO_E_NEED_PROBE;
	n = h3c_nand_auto_collect(id, model, c, H3C_NAND_AUTO_MAX_CAND, &rows);
	if (n != 2U)
		return H3C_NAND_AUTO_E_UNKNOWN;
	c4 = c[0].mode == 4U ? &c[0] : &c[1];
	c8 = c[0].mode == 8U ? &c[0] : &c[1];
	if (c4->mode != 4U || c8->mode != 8U)
		return H3C_NAND_AUTO_E_UNKNOWN;
	ret = h3c_nand_auto_count(ops, c4, &v4);
	if (ret)
		return ret;
	ret = h3c_nand_auto_count(ops, c8, &v8);
	if (ret)
		return ret;
	mode = h3c_nand_ecc_unique_mode(v4 >= H3C_NAND_AUTO_MIN_EVIDENCE,
					v8 >= H3C_NAND_AUTO_MIN_EVIDENCE);
	/* Any valid page in the other format contradicts the choice. */
	if ((mode == 4U && v8) || (mode == 8U && v4) || !mode)
		return H3C_NAND_AUTO_E_UNKNOWN;
	if (ops->set_format(ops->ctx, mode, mode == 4U ? c4->spare : c8->spare))
		return H3C_NAND_AUTO_E_IO;
	return h3c_nand_auto_finish(mode == 4U ? c4 : c8, 1, v4, v8, res);
}
