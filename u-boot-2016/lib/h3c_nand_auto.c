// SPDX-License-Identifier: GPL-2.0+
/* U-Boot glue for run-time NAND profile selection (see h3c_nand_auto.h). */
#include <common.h>
#include <malloc.h>
#include <asm/errno.h>
#include <linux/mtd/mtd.h>
#include <nand.h>
#include <asm/arch-qca-common/qpic_nand.h>
#include <h3c_nand_auto.h>
#include <h3c_nand_ecc.h>

enum { AUTO_IDLE = 0, AUTO_PENDING, AUTO_OK, AUTO_FAILED };

static struct {
	int state;
	unsigned char id[2];
	const char *model;
	const struct h3c_nand_catalog_profile *row;
	unsigned int mode;
} st;

void h3c_nand_auto_reset(void)
{
	memset(&st, 0, sizeof(st));
}

int h3c_nand_auto_early(const unsigned char id[2], const char *model,
			const struct h3c_nand_catalog_profile **row,
			unsigned int *mode)
{
	struct h3c_nand_auto_result res;
	int ret;

	h3c_nand_auto_reset();
	st.state = AUTO_FAILED;
	if (!id || !model || !row || !mode)
		return 0;
	st.id[0] = id[0];
	st.id[1] = id[1];
	st.model = model;
	ret = h3c_nand_auto_resolve_catalog(id, model, &res);
	if (ret == H3C_NAND_AUTO_E_NEED_PROBE) {
		st.state = AUTO_PENDING;
		return 0;
	}
	if (ret) {
		printf("H3C NAND AUTO: no profile for %02x:%02x %s (%d)\n",
		       id[0], id[1], model, ret);
		return 0;
	}
	st.state = AUTO_OK;
	st.row = res.row;
	st.mode = res.mode;
	*row = res.row;
	*mode = res.mode;
	return 1;
}

static int auto_set_format(void *ctx, unsigned int bits, unsigned int spare)
{
	(void)ctx;
	return qpic_nand_auto_set_format(bits, spare);
}

static int auto_read_page(void *ctx, unsigned long long offset,
			  unsigned char *buf, unsigned int len)
{
	struct mtd_info *mtd = ctx;
	unsigned int failed_before = mtd->ecc_stats.failed;
	size_t retlen = 0;
	int ret = mtd_read(mtd, offset, len, &retlen, buf);

	if (ret == -EBADMSG || mtd->ecc_stats.failed != failed_before)
		return H3C_NAND_AUTO_READ_ECC;
	if ((ret && ret != -EUCLEAN) || retlen != len)
		return ret < 0 ? ret : -EIO;
	return H3C_NAND_AUTO_READ_OK;
}

void h3c_nand_auto_run(void)
{
	struct mtd_info *mtd = &nand_info[CONFIG_QPIC_NAND_NAND_INFO_IDX];
	struct mtd_ecc_stats saved = mtd->ecc_stats;
	struct h3c_nand_auto_ops ops;
	struct h3c_nand_auto_result res;
	unsigned int old_bits = mtd->ecc_strength;
	unsigned int old_spare = h3c_qpic_nand_physical_spare();
	int ret;

	if (st.state == AUTO_PENDING) {
		memset(&ops, 0, sizeof(ops));
		ops.ctx = mtd;
		ops.set_format = auto_set_format;
		ops.read_page = auto_read_page;
		ops.buf_len = H3C_NAND_AUTO_PAGE_BYTES;
		ops.buf = memalign(ARCH_DMA_MINALIGN, ops.buf_len);
		if (!ops.buf) {
			st.state = AUTO_FAILED;
		} else {
			ret = h3c_nand_auto_resolve(st.id, st.model, &ops, &res);
			free(ops.buf);
			mtd->ecc_stats = saved;
			if (ret) {
				st.state = AUTO_FAILED;
				printf("H3C NAND AUTO: boot-chain ECC not unique (%d)\n",
				       ret);
				/* Leave the controller as it was found, not in
				 * the last format that was tried. */
				if ((old_bits == 4U || old_bits == 8U) && old_spare &&
				    qpic_nand_auto_set_format(old_bits, old_spare))
					printf("H3C NAND AUTO: could not restore ECC%u\n",
					       old_bits);
			} else {
				st.state = AUTO_OK;
				st.row = res.row;
				st.mode = res.mode;
				qpic_nand_auto_set_load_bits(res.mode);
				printf("H3C NAND AUTO: %s ECC%u (ECC4 pages %u, ECC8 pages %u)\n",
				       res.row->profile_id, res.mode,
				       res.valid4, res.valid8);
			}
		}
	}
	if (st.state != AUTO_OK) {
		st.row = NULL;
		st.mode = 0;
		st.state = AUTO_FAILED;
		printf("H3C NAND AUTO: no profile selected, NAND writes stay rejected\n");
	}
}

int h3c_nand_auto_ok(void)
{
	return st.state == AUTO_OK && st.row && (st.mode == 4U || st.mode == 8U);
}

const struct h3c_nand_catalog_profile *h3c_nand_auto_row(void)
{
	return h3c_nand_auto_ok() ? st.row : NULL;
}

unsigned int h3c_nand_auto_mode(void)
{
	return h3c_nand_auto_ok() ? st.mode : 0;
}
