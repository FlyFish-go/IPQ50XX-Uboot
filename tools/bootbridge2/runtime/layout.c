// SPDX-License-Identifier: GPL-2.0-or-later
#include "layout.h"
#include <string.h>

static const struct bb_layout layouts[] = {
	{ "nx30", "A|B|C|D", { 0x900000, 0x3100000 }, 0x2800000, 0 },
	{ "nx54", "NX54", { 0x900000, 0x3640000 }, 0x2d40000, 1 },
};

static const struct bb_part_spec startup[] = {
	{ "0:SBL1", "startup", 0, 0x80000, 0 },
	{ "0:MIBIB", "startup", 0x80000, 0x80000, 0 },
	{ "0:BOOTCONFIG", "startup", 0x100000, 0x40000, 0 },
	{ "0:BOOTCONFIG1", "startup", 0x140000, 0x40000, 0 },
	{ "0:QSEE", "startup", 0x180000, 0x100000, 0 },
	{ "0:QSEE_1", "startup", 0x280000, 0x100000, 0 },
	{ "0:DEVCFG", "startup", 0x380000, 0x40000, 0 },
	{ "0:DEVCFG_1", "startup", 0x3c0000, 0x40000, 0 },
	{ "0:CDT", "startup", 0x400000, 0x40000, 0 },
	{ "0:CDT_1", "startup", 0x440000, 0x40000, 0 },
	{ "0:APPSBLENV", "startup", 0x480000, 0x80000, 0 },
	{ "0:APPSBL", "startup", 0x500000, 0x140000, 0 },
	{ "0:APPSBL_1", "startup", 0x640000, 0x140000, 0 },
	{ "0:ART", "startup", 0x780000, 0x100000, 0 },
	{ "0:TRAINING", "startup", 0x880000, 0x80000, 0 },
};

const struct bb_layout *bb_layout_slots(const struct bb_flash *a, const struct bb_flash *b)
{
	if (!a || !b) return NULL;
	for (unsigned i = 0; i < sizeof(layouts) / sizeof(layouts[0]); i++) {
		const struct bb_layout *l = &layouts[i];
		if (a->size == l->slot_size && b->size == l->slot_size &&
		    ((a->offset == l->slot_offset[0] && b->offset == l->slot_offset[1]) ||
		     (b->offset == l->slot_offset[0] && a->offset == l->slot_offset[1])))
			return l;
	}
	return NULL;
}

const struct bb_layout *bb_layout_board(const char *board)
{
	for (unsigned i = 0; i < sizeof(layouts) / sizeof(layouts[0]); i++)
		for (const char *p = layouts[i].boards; *p;) {
			size_t n = strcspn(p, "|");
			if (strlen(board) == n && !strncmp(board, p, n)) return &layouts[i];
			p += n + (p[n] == '|');
		}
	return NULL;
}

int bb_part_matches(const struct bb_part_spec *p, const struct bb_flash *f)
{
	return f && f->offset == p->offset && f->size == p->size &&
		f->erase_size == 0x20000 && f->page_size == 2048;
}

unsigned bb_layout_backup(const struct bb_layout *l, struct bb_part_spec *out, unsigned max)
{
	static const char *const pers[] = { "pdt_data", "pdt_data_1", "exp", "plugin" };
	unsigned n = sizeof(startup) / sizeof(startup[0]);
	if (!l || max < n + 6) return 0;
	memcpy(out, startup, sizeof(startup));
	if (l->full_backup)
		for (unsigned i = 0; i < 2; i++)
			out[n++] = (struct bb_part_spec){ i ? "rootfs_1" : "rootfs", "system-slot",
				l->slot_offset[i], l->slot_size, 0 };
	uint32_t end = l->slot_offset[1] + l->slot_size;
	for (unsigned i = 0; i < (l->full_backup ? 3u : 4u); i++) {
		uint32_t size = i < 2 ? 0x900000 : 0x100000;
		out[n++] = (struct bb_part_spec){ pers[i], "oem-persistent-data", end, size,
			!l->full_backup };
		end += size;
	}
	return n;
}
