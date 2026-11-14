/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * Xiaomi miwifi slot rules as pure functions of the environment flags.
 *
 *   L = flag_last_success, T0/T1 = flag_try_sys1/2_failed (slot 0/1),
 *   O = flag_ota_reboot, S = flag_boot_success (may be absent),
 *   R = flag_boot_rootfs (an output, handled by the caller).
 *
 * lib/slot_xiaomi.c reads and writes the environment; the decisions are made
 * here so that test/slot_xiaomi_hosttest.c can check them against the table
 * of the stock bootmiwifi logic.
 */
#ifndef SLOT_XIAOMI_CORE_H
#define SLOT_XIAOMI_CORE_H

#ifdef __UBOOT__
#include <common.h>
#else
#include <stdint.h>
#endif

/* Reset-reason register of the stock U-Boot; Linux leaves 0x10 there after a
 * panic or watchdog reset. */
#define XIAOMI_RESET_REASON_REG		0x0193d100
#define XIAOMI_RESET_REASON_CRASH	0x10

struct xiaomi_flags {
	unsigned long t0, t1;	/* flag_try_sys1_failed, flag_try_sys2_failed */
	unsigned long ota;	/* flag_ota_reboot */
	unsigned long last;	/* flag_last_success */
	int success_set;	/* flag_boot_success present */
	unsigned long success;
};

struct xiaomi_select {
	unsigned int slot;
	int drop_ota;		/* delete flag_ota_reboot and flag_upgrade_push */
};

/* Stock get_boot_slot(). Values above 1 select slot 0 and are never written. */
static inline struct xiaomi_select xiaomi_select_core(const struct xiaomi_flags *f)
{
	struct xiaomi_select r = { 0, 0 };

	if (f->t0 > 1 || f->t1 > 1 || f->ota > 1 || f->last > 1)
		return r;
	if (f->ota) {
		if (f->success_set && f->success == 0) {
			r.slot = f->last;	/* the OTA system never came up */
			r.drop_ota = 1;
			return r;
		}
		r.slot = 1 - f->last;
		return r;
	}
	r.slot = (f->last ? f->t1 : f->t0) ? 1 - f->last : f->last;
	return r;
}

struct xiaomi_failure {
	unsigned int mark_slot;	/* set flag_try_sys<mark_slot+1>_failed=1 */
	int both_failed;	/* the other slot is marked as well: do not reset */
};

/*
 * A boot of "slot" failed. Stock marks the slot that failed for a bad image,
 * but always slot 0 when UBI cannot attach or the partition is missing, which
 * resets forever when that was slot 1. We mark the slot that really failed.
 * flag_ota_reboot is cleared by the caller in every case.
 */
static inline struct xiaomi_failure xiaomi_failure_core(const struct xiaomi_flags *f,
							 unsigned int slot)
{
	struct xiaomi_failure r;

	r.mark_slot = slot;
	r.both_failed = (slot ? f->t0 : f->t1) != 0;
	return r;
}

/*
 * Flags for "boot slot as a pending OTA", as stock OTA leaves them: the other
 * slot (the one that runs now) is the last success, slot is not marked failed,
 * flag_ota_reboot=1 and flag_boot_success=1 (an explicit 0 would cancel the
 * OTA). The other slot's failure mark is kept: rolling back to a slot that
 * failed would only loop.
 */
static inline void xiaomi_pending_ota(struct xiaomi_flags *f, unsigned int slot)
{
	f->last = 1 - slot;
	if (slot)
		f->t1 = 0;
	else
		f->t0 = 0;
	f->ota = 1;
	f->success_set = 1;
	f->success = 1;
}

/*
 * A pending OTA (O=1) whose slot already booted once (R is that slot, written
 * on the first try) and came back without a crash record ran fine: make it
 * the last success, as stock boot_check would. Systems that never touch the
 * flags (OpenWrt) are confirmed this way instead of staying pending forever.
 */
static inline int xiaomi_ota_confirmed(const struct xiaomi_flags *f,
				       unsigned long rootfs, uint32_t reset_reason)
{
	unsigned long slot = 1 - f->last;

	if (f->ota != 1 || f->last > 1 || f->t0 > 1 || f->t1 > 1)
		return 0;
	if (f->success_set && f->success == 0)
		return 0;
	if ((slot ? f->t1 : f->t0) || rootfs != slot)
		return 0;
	return reset_reason != XIAOMI_RESET_REASON_CRASH;
}

/* Stock row 11: a RAM crash record means the system that just ran died, so a
 * pending OTA flag must go before the slot is decided. */
static inline int xiaomi_crash_drops_ota(uint32_t reset_reason, unsigned long ota)
{
	return reset_reason == XIAOMI_RESET_REASON_CRASH && ota != 0;
}

#endif /* SLOT_XIAOMI_CORE_H */
