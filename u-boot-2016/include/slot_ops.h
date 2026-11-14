/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * How a board records which system slot boots.
 *
 * Common code asks here and never names the mechanism. One backend is built
 * into each image, chosen in Kconfig, because an image serves one device.
 */
#ifndef __SLOT_OPS_H__
#define __SLOT_OPS_H__

#include <linux/errno.h>

#ifdef CONFIG_SLOT_BACKEND_SINGLE

static inline bool slot_info_available(void) { return false; }
static inline unsigned int slot_active_rootfs(void) { return 0; }
static inline int slot_default_rootfs(void) { return 0; }
/* Macros, not inlines: keeps other images byte-identical. */
#define slot_prepare_boot()	0
#define slot_boot_failed()	do { } while (0)

/* Rescue page: one system, nothing to choose. */
static inline unsigned int slot_count(void) { return 1; }
static inline const char *slot_part_name(unsigned int slot) { return "rootfs"; }
static inline int slot_set_default(unsigned int slot) { return -ENOSYS; }

#elif defined(CONFIG_SLOT_BACKEND_XIAOMI)

/* Xiaomi miwifi: U-Boot environment flags, see lib/slot_xiaomi.c. */
unsigned int xiaomi_slot_select(void);
static inline bool slot_info_available(void) { return true; }
static inline unsigned int slot_active_rootfs(void) { return xiaomi_slot_select(); }
static inline int slot_default_rootfs(void) { return xiaomi_slot_select(); }
/* NAND boot: point rootfs and bootargs at the slot and record it. */
int slot_prepare_boot(void);
/* The kernel could not be loaded or started: mark the slot, maybe reset. */
void slot_boot_failed(void);

/* Rescue page. Slot n is always partition rootfs (0) or rootfs_1 (1). */
int xiaomi_slot_choose(unsigned int slot);
static inline unsigned int slot_count(void) { return 2; }
static inline const char *slot_part_name(unsigned int slot)
{
	return slot ? "rootfs_1" : "rootfs";
}
/* Boot slot from now on (flags as after a clean boot of it); saves the env. */
static inline int slot_set_default(unsigned int slot) { return xiaomi_slot_choose(slot); }

#else /* Qualcomm BOOTCONFIG */

#include <bootconfig.h>
#include <asm/arch-qca-common/smem.h>

/* True when SBL handed U-Boot a valid dual-boot table. */
static inline bool slot_info_available(void)
{
	return smem_bootconfig_info() == 0;
}

/* The rootfs slot SBL chose for this boot, 0 or 1. Needs slot_info_available(). */
static inline unsigned int slot_active_rootfs(void)
{
	return get_rootfs_active_partition();
}

/* The rootfs slot stored in flash, 0 or 1, or a negative error. */
static inline int slot_default_rootfs(void)
{
	return get_bootconfig("rootfs");
}

/* SBL already swapped the partition names; nothing to do. Macros, not
 * inlines: keeps other images byte-identical. */
#define slot_prepare_boot()	0
#define slot_boot_failed()	do { } while (0)

/*
 * Rescue page. Slot n means BOOTCONFIG rootfs value n. SBL gives the name
 * "rootfs" to the slot it booted this time and "rootfs_1" to the other one,
 * so the names follow the active slot, not the flash order.
 */
static inline unsigned int slot_count(void)
{
	return slot_info_available() ? 2 : 1;
}
static inline const char *slot_part_name(unsigned int slot)
{
	if (!slot_info_available())
		return "rootfs";
	return slot == slot_active_rootfs() ? "rootfs" : "rootfs_1";
}
/* Boot slot from now on: the firmware group (rootfs, HLOS, WIFIFW, BTFW) as
 * stock sysupgrade switches it; refuses an erased target, syncs both copies. */
static inline int slot_set_default(unsigned int slot)
{
	return set_bootconfig("firmware", slot);
}

#endif
#endif /* __SLOT_OPS_H__ */
