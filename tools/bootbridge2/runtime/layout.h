/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef BB_LAYOUT_H
#define BB_LAYOUT_H
#include "flash.h"

struct bb_part_spec {
	const char *name, *role;
	uint32_t offset, size;
	int optional;
};

/* Layout is a fact about partitions, never permission to install or return. */
struct bb_layout {
	const char *id, *boards;
	uint32_t slot_offset[2], slot_size;
	int full_backup;
};

const struct bb_layout *bb_layout_slots(const struct bb_flash *a, const struct bb_flash *b);
const struct bb_layout *bb_layout_board(const char *board);
unsigned bb_layout_backup(const struct bb_layout *l, struct bb_part_spec *out, unsigned max);
int bb_part_matches(const struct bb_part_spec *p, const struct bb_flash *f);
/* SBL renames failsafe pairs ("X" <-> "X_1", e.g. rootfs, 0:APPSBL) after the
 * selector flips, so a partition found by physical offset may carry its
 * partner's name. Nonzero when `name` is p->name or that pair partner. */
int bb_part_name_ok(const struct bb_part_spec *p, const char *name);
#endif
