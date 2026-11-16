/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef BB_FLASH_MTD_H
#define BB_FLASH_MTD_H

#include "flash.h"

/* Index of the MTD partition with this name, or (name == NULL) at this
 * physical offset. Returns -1 if not found. */
int bb_mtd_find(const char *name, uint32_t offset);

/* Open /dev/mtd<idx>. Returns 0 or a negative errno. */
int bb_mtd_open(int idx, int writable, struct bb_flash *f);

int bb_mtd_ecc_stats(void *ctx, uint32_t *failed, uint32_t *corrected);
int bb_mtd_geometry(int idx, const struct bb_flash *f, unsigned oob, unsigned ecc);

#endif
