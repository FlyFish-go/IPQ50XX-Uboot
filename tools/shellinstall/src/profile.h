/* SPDX-License-Identifier: GPL-2.0-or-later */
/* What the installer must find on a model before it writes anything.
 * Source of each value: the model's verified TTL recon (partition table from
 * smeminfo == Linux ofpart, OEM marker from its rootfs). */
#ifndef IPQI_PROFILE_H
#define IPQI_PROFILE_H

#include <stdint.h>

struct ipqi_layout_part {
	const char *name;
	uint32_t offset, size;
};

enum ipqi_slots {
	IPQI_SLOTS_BOOTCONFIG,	/* QCA BOOTCONFIG: 0:APPSBL selector decides the active copy */
	IPQI_SLOTS_SINGLE,	/* one APPSBL only */
};

struct ipqi_profile {
	const char *id;			/* devices/<id>.yaml */
	const char *title;
	const char *dt_model;		/* substring of /proc/device-tree/model */
	const char *marker_file;	/* OEM firmware marker, file + substring */
	const char *marker_text;
	uint32_t erase_size, page_size;
	const struct ipqi_layout_part *layout;	/* every entry must match exactly */
	unsigned layout_len;
	const char *const *backup;	/* partitions saved before writing, NULL ended */
	enum ipqi_slots slots;
	const char *payload;		/* package entry holding this model's U-Boot */
};

extern const struct ipqi_profile ipqi_profiles[];
extern const unsigned ipqi_profiles_len;

#endif
