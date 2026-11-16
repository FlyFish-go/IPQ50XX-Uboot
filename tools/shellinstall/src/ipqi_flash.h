/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Partition access for the system installer. On a device this is /dev/mtdN
 * through BootBridge2's flash_mtd backend. With IPQI_SIM=<dir> everything,
 * including the files the checks read, comes from a simulated device:
 *   <dir>/nand.bin     whole NAND main area
 *   <dir>/parts.txt    "name offset size erase page ro" per line
 *   <dir>/bad.txt      bad block offsets (optional)
 *   <dir>/fs/...       stands in for / (proc, sys, etc files) */
#ifndef IPQI_FLASH_H
#define IPQI_FLASH_H

#include "../../bootbridge2/runtime/flash.h"

#define IPQI_MAX_PARTS 64

struct ipqi_part_info {
	int idx;
	char name[32];
	uint32_t offset, size, erase_size, page_size;
	int writable;		/* kernel allows writes (MTD_WRITEABLE) */
};

int ipqi_sim(void);
/* Path of a system file, under the simulated root when IPQI_SIM is set. */
const char *ipqi_path(const char *p, char *buf, size_t len);
/* All NAND partitions. Returns the count. */
int ipqi_parts(struct ipqi_part_info *out, int max);
int ipqi_open(int idx, int writable, struct bb_flash *f);

#endif
