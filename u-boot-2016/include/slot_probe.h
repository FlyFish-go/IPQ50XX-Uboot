/* SPDX-License-Identifier: GPL-2.0 */
/*
 * What system sits in a rootfs slot, read from the slot itself on any board:
 * the kernel version from the kernel image name and the release text from
 * the root file system. No table of known images: a new vendor release needs
 * no new U-Boot.
 */
#ifndef __SLOT_PROBE_H__
#define __SLOT_PROBE_H__
#include <stddef.h>

struct slot_probe {
	char system[97];	/* release text, e.g. "OpenWrt 24.10.0"; "" if none */
	char kernel[33];	/* e.g. "6.6.73"; "" if none */
	char error[48];		/* "" when the slot was read */
	int env_lost;		/* the environment could not be restored */
};

/* Read-only look at the UBI in [offset, offset + size), named part_name
 * ("rootfs" or "rootfs_1"). Fills p; returns 0 or a negative errno. */
int slot_probe_read(const char *part_name, unsigned long long offset,
		    unsigned long long size,
		    struct slot_probe *p);

/* The version after the first "Linux-" (as in "ARM OpenWrt Linux-6.6.73",
 * the FIT kernel description or the legacy uImage name): 0 or -ENOENT. */
int slot_probe_kernel_version(const unsigned char *buf, size_t len,
			      char *out, size_t out_len);
#endif
