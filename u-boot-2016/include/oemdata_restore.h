/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * Restore of the four H3C OEM data partitions from a flash backup.
 *
 * pdt_data, pdt_data_1, exp and plugin sit at fixed places of the OEM table
 * that every RT3000-family unit shares. In the OEM and the 80 MiB layouts
 * they are named SMEM partitions; in the extra-large single layout they are
 * the tail of the one big rootfs, so a restore (before switching back to
 * the OEM table) writes into that rootfs extent.
 *
 * The file is chosen by name: the flash backup page names its download
 * smem_<partition>.bin. Pure logic; the caller reads the layout and does the
 * flash work.
 */
#ifndef OEMDATA_RESTORE_H
#define OEMDATA_RESTORE_H

#ifdef __UBOOT__
#include <common.h>
#else
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#endif

struct oemdata_part {
	const char *name;
	uint64_t off, size;
};

static const struct oemdata_part oemdata_parts[] = {
	{ "pdt_data",   0x05900000ULL, 0x00600000ULL },
	{ "pdt_data_1", 0x05f00000ULL, 0x00600000ULL },
	{ "exp",        0x06500000ULL, 0x00100000ULL },
	{ "plugin",     0x06600000ULL, 0x01700000ULL },
};
#define OEMDATA_NPARTS	(sizeof(oemdata_parts) / sizeof(oemdata_parts[0]))

/* rootfs of the extra-large single layout: 0x900000 .. 0x7d00000 */
#define OEMDATA_XL_ROOTFS_OFF	0x00900000ULL
#define OEMDATA_XL_ROOTFS_SIZE	0x07400000ULL

/* "<dir>/smem_pdt_data.bin", "pdt_data.2.bin", ...; anything else is NULL. */
static inline const struct oemdata_part *oemdata_find(const char *filename)
{
	const char *b = filename, *p, *dot;
	size_t n, len, i;

	if (!filename)
		return NULL;
	for (p = filename; *p; p++)
		if (*p == '/' || *p == '\\')
			b = p + 1;
	if (!strncmp(b, "smem_", 5))
		b += 5;
	len = strlen(b);
	if (len < 5 || strcmp(b + len - 4, ".bin"))
		return NULL;
	dot = strchr(b, '.');
	n = dot - b;
	for (i = 0; i < OEMDATA_NPARTS; i++)
		if (strlen(oemdata_parts[i].name) == n &&
		    !memcmp(oemdata_parts[i].name, b, n))
			return &oemdata_parts[i];
	return NULL;
}

/*
 * The restore erases the whole extent, so only a backup of the whole
 * partition may be written back: the full extent (a raw dump), or its good
 * blocks (the backup page skips bad blocks). good = the good-block bytes of
 * the extent on this unit now.
 */
static inline int oemdata_size_ok(const struct oemdata_part *p, uint64_t size,
				  uint64_t good)
{
	return p && size && (size == p->size || size == good);
}

struct oemdata_smem {
	int have;		/* the SMEM table has this entry */
	uint64_t off, size;
};

struct oemdata_window {
	const char *name;	/* SMEM name the write window is opened on */
	uint64_t off, size;
};

#define OEMDATA_OK	0
#define OEMDATA_EXDEV	(-18)	/* layout does not hold this partition */

/*
 * Where may p be written? named = the SMEM entry called p->name, rootfs =
 * the SMEM entry "rootfs", single = the layout is one rootfs (not dual).
 * A named entry must be exactly the OEM extent. Without it the only
 * accepted place is the exact XL rootfs, which contains the OEM extent.
 */
static inline int oemdata_window(const struct oemdata_part *p,
				 const struct oemdata_smem *named,
				 const struct oemdata_smem *rootfs, int single,
				 struct oemdata_window *w)
{
	if (!p || !named || !rootfs || !w)
		return OEMDATA_EXDEV;
	if (named->have) {
		if (named->off != p->off || named->size != p->size)
			return OEMDATA_EXDEV;
		w->name = p->name;
		w->off = p->off;
		w->size = p->size;
		return OEMDATA_OK;
	}
	if (!single || !rootfs->have || rootfs->off != OEMDATA_XL_ROOTFS_OFF ||
	    rootfs->size != OEMDATA_XL_ROOTFS_SIZE ||
	    p->off < rootfs->off || p->off + p->size > rootfs->off + rootfs->size)
		return OEMDATA_EXDEV;
	w->name = "rootfs";
	w->off = rootfs->off;
	w->size = rootfs->size;
	return OEMDATA_OK;
}

#endif /* OEMDATA_RESTORE_H */
