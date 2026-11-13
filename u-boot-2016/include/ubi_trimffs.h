/* SPDX-License-Identifier: GPL-2.0+ */
/*
 * Page plan for writing a UBI image into a NAND partition.
 *
 * Programming an all-0xff page leaves it "written" for the controller, and
 * UBI/UBIFS later fails to use it (ECC errors on first real write). So pages
 * that are entirely 0xff in the image are skipped (the erased page is left
 * alone), bad blocks are skipped forward, and the plan is refused up front
 * when the good blocks of the partition cannot hold the image.
 *
 * Pure logic, no U-Boot dependencies: the caller supplies the bad-block test
 * and receives one callback per page.
 */
#ifndef UBI_TRIMFFS_H
#define UBI_TRIMFFS_H

#ifdef __UBOOT__
#include <common.h>
#else
#include <stddef.h>
#include <stdint.h>
#endif

#define UBI_TRIMFFS_OK		0
#define UBI_TRIMFFS_EINVAL	(-1)
#define UBI_TRIMFFS_ENOSPC	(-2)	/* image does not fit the good blocks */
#define UBI_TRIMFFS_EEMIT	(-3)	/* callback failed */

struct ubi_trimffs_stats {
	uint32_t pages_written;
	uint32_t pages_skipped;
	uint32_t blocks_needed;
	uint32_t blocks_good;
};

/* Returns nonzero when erase block <blk> (0-based, in the partition) is bad. */
typedef int (*ubi_trimffs_isbad_fn)(void *ctx, uint32_t blk);
/*
 * One call per image page, in order. phys is the byte offset inside the
 * partition, img_off/n the slice of the image (n < writesize only for the
 * final partial page, which the caller pads with 0xff). write==0: skip.
 * Return nonzero to abort.
 */
typedef int (*ubi_trimffs_emit_fn)(void *ctx, uint64_t phys, size_t img_off,
				   uint32_t n, int write);

static inline int ubi_trimffs_all_ff(const uint8_t *p, uint32_t n)
{
	while (n--)
		if (*p++ != 0xff)
			return 0;
	return 1;
}

static inline int ubi_trimffs_plan(const uint8_t *img, size_t len,
				   uint32_t writesize, uint32_t erasesize,
				   uint32_t nblocks,
				   ubi_trimffs_isbad_fn isbad, void *bctx,
				   ubi_trimffs_emit_fn emit, void *ectx,
				   struct ubi_trimffs_stats *st)
{
	struct ubi_trimffs_stats s = { 0, 0, 0, 0 };
	uint32_t pages_per_block, blk, good = 0, cur = 0;
	size_t off = 0;
	uint32_t pg_in_block = 0;
	int have_blk = 0;

	if (!img || !writesize || !erasesize || erasesize % writesize ||
	    !isbad || !emit)
		return UBI_TRIMFFS_EINVAL;
	pages_per_block = erasesize / writesize;

	for (blk = 0; blk < nblocks; blk++)
		if (!isbad(bctx, blk))
			good++;
	s.blocks_good = good;
	s.blocks_needed = (uint32_t)((len + erasesize - 1) / erasesize);
	if (s.blocks_needed > good) {
		if (st)
			*st = s;
		return UBI_TRIMFFS_ENOSPC;
	}

	while (off < len) {
		uint32_t n = writesize;
		int write;

		if (!have_blk || pg_in_block == pages_per_block) {
			while (cur < nblocks && isbad(bctx, cur))
				cur++;
			if (cur >= nblocks)	/* cannot happen after the count */
				return UBI_TRIMFFS_ENOSPC;
			have_blk = 1;
			pg_in_block = 0;
			cur++;
		}
		if (len - off < n)
			n = (uint32_t)(len - off);
		write = !ubi_trimffs_all_ff(img + off, n);
		if (emit(ectx, (uint64_t)(cur - 1) * erasesize +
			 (uint64_t)pg_in_block * writesize, off, n, write))
			return UBI_TRIMFFS_EEMIT;
		if (write)
			s.pages_written++;
		else
			s.pages_skipped++;
		off += n;
		pg_in_block++;
	}
	if (st)
		*st = s;
	return UBI_TRIMFFS_OK;
}

#endif /* UBI_TRIMFFS_H */
