// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Xiaomi dual-system slot backend (CR8806 and other miwifi IPQ50xx units).
 *
 * The SBL never swaps rootfs/rootfs_1 here. The stock U-Boot command
 * bootmiwifi picks the slot from flags in the U-Boot environment, which
 * stock Linux edits with /usr/sbin/nvram. These rules copy it, so stock
 * OTA, boot_check and rollback keep working:
 *
 *   L = flag_last_success, T0/T1 = flag_try_sys1/2_failed (slot 0/1),
 *   O = flag_ota_reboot, S = flag_boot_success, R = flag_boot_rootfs.
 *
 * Any of L, T0, T1, O above 1 selects slot 0. O=1 tries the new slot 1-L,
 * unless S is explicitly 0: then L, and O is dropped. Otherwise L, or 1-L
 * when T[L] is set. R is an output, saved when it differs from the slot
 * being booted: stock Linux reads it to pick the OTA target and the slot to
 * blame on failure, and sets L, S and T itself after a good boot.
 *
 * Deliberate differences from stock: a failed boot marks the slot that
 * really failed (stock blames slot 0 for UBI errors and can reset forever),
 * and once both slots are marked failed U-Boot stays in web recovery
 * instead of resetting.
 */
#include <common.h>
#include <command.h>
#include <errno.h>
#include <slot_ops.h>
#include <asm/arch-qca-common/smem.h>

#define XM_ROOTARGS "root=mtd:ubi_rootfs rootfstype=squashfs"

static unsigned long xm_flag(const char *name)
{
	const char *v = getenv(name);

	return v ? simple_strtoul(v, NULL, 10) : 0;
}

static void xm_set_flag(const char *name, unsigned int val)
{
	char buf[12];

	snprintf(buf, sizeof(buf), "%u", val);
	setenv(name, buf);
}

unsigned int xiaomi_slot_select(void)
{
	unsigned long t0 = xm_flag("flag_try_sys1_failed");
	unsigned long t1 = xm_flag("flag_try_sys2_failed");
	unsigned long ota = xm_flag("flag_ota_reboot");
	unsigned long last = xm_flag("flag_last_success");
	const char *bs;

	if (t0 > 1 || t1 > 1 || ota > 1 || last > 1)
		return 0;
	if (ota) {
		bs = getenv("flag_boot_success");
		if (bs && simple_strtoul(bs, NULL, 10) == 0) {
			puts("Xiaomi slots: OTA boot failed, back to the old system\n");
			setenv("flag_ota_reboot", NULL);
			setenv("flag_upgrade_push", NULL);
			return last;
		}
		return 1 - last;
	}
	if (last ? t1 : t0)
		return 1 - last;
	return last;
}

int slot_prepare_boot(void)
{
	qca_smem_flash_info_t *sfi = &qca_smem_flash_info;
	unsigned int slot = xiaomi_slot_select();
	char *name = slot ? "rootfs_1" : "rootfs";
	const char *v;
	char args[128];
	uint32_t start, size;

	if (smem_getpart(name, &start, &size)) {
		printf("Xiaomi slots: no %s partition\n", name);
		return -ENOENT;
	}
	qca_set_part_entry(name, sfi, &sfi->rootfs, start, size);
	printf("Xiaomi slots: booting %s (slot %u)\n", name, slot);

	snprintf(args, sizeof(args), "ubi.mtd=%s " XM_ROOTARGS, name);
	setenv("fsbootargs", args);
	/* Leave the environment as stock does, in case it gets saved. */
	snprintf(args, sizeof(args), "ubi.mtd=%s " XM_ROOTARGS " rootwait", name);
	setenv("bootargs", args);

	v = getenv("flag_boot_rootfs");
	if (!v || simple_strtoul(v, NULL, 10) != slot) {
		xm_set_flag("flag_boot_rootfs", slot);
		if (saveenv())
			puts("Xiaomi slots: cannot save flag_boot_rootfs\n");
	}

	/* The command line is bootargs + fsbootargs: keep only the extras. */
	v = getenv("uart_en");
	if (v && strcmp(v, "0")) {
		snprintf(args, sizeof(args), "uart_en=%s", v);
		setenv("bootargs", args);
	} else {
		setenv("bootargs", NULL);
	}
	return 0;
}

void slot_boot_failed(void)
{
	unsigned int slot = xiaomi_slot_select();
	char name[24];

	snprintf(name, sizeof(name), "flag_try_sys%u_failed", slot + 1);
	xm_set_flag(name, 1);
	xm_set_flag("flag_ota_reboot", 0);
	if (saveenv()) {
		puts("Xiaomi slots: cannot save the failure flag\n");
		return;
	}
	if (xm_flag(slot ? "flag_try_sys1_failed" : "flag_try_sys2_failed")) {
		puts("Xiaomi slots: both systems failed to boot, staying in recovery\n");
		return;
	}
	printf("Xiaomi slots: slot %u failed to boot, trying the other one\n", slot);
	run_command("reset", 0);
}

/*
 * Make slot the one that boots next, robustly: with L = R = slot, both
 * failure flags clear and no OTA pending, the rules above return slot.
 */
static int xiaomi_slot_set_next(unsigned int slot)
{
	xm_set_flag("flag_last_success", slot);
	xm_set_flag("flag_boot_rootfs", slot);
	xm_set_flag("flag_try_sys1_failed", 0);
	xm_set_flag("flag_try_sys2_failed", 0);
	xm_set_flag("flag_ota_reboot", 0);
	xm_set_flag("flag_boot_success", 1);
	return saveenv();
}

static int do_xiaomi_slot(cmd_tbl_t *cmdtp, int flag, int argc,
			  char *const argv[])
{
	unsigned long slot;

	if (argc == 1) {
		printf("next boot: slot %u (%s)\n", xiaomi_slot_select(),
		       xiaomi_slot_select() ? "rootfs_1" : "rootfs");
		return CMD_RET_SUCCESS;
	}
	if (argc != 3 || strcmp(argv[1], "select"))
		return CMD_RET_USAGE;
	slot = simple_strtoul(argv[2], NULL, 10);
	if (slot > 1 || strlen(argv[2]) != 1)
		return CMD_RET_USAGE;
	if (xiaomi_slot_set_next(slot)) {
		puts("xiaomi_slot: cannot save the environment\n");
		return CMD_RET_FAILURE;
	}
	printf("next boot: slot %lu (%s)\n", slot, slot ? "rootfs_1" : "rootfs");
	return CMD_RET_SUCCESS;
}

U_BOOT_CMD(xiaomi_slot, 3, 0, do_xiaomi_slot,
	   "show or choose the Xiaomi system slot for the next boot",
	   "\n    - show the slot the flags select\n"
	   "xiaomi_slot select <0|1>\n"
	   "    - boot rootfs (0) or rootfs_1 (1) from now on; saves the environment");

/* The stock environment says bootcmd=bootmiwifi; keep it working. */
static int do_bootmiwifi(cmd_tbl_t *cmdtp, int flag, int argc,
			 char *const argv[])
{
	return run_command("bootipq", 0) ? CMD_RET_FAILURE : CMD_RET_SUCCESS;
}

U_BOOT_CMD(bootmiwifi, 1, 0, do_bootmiwifi,
	   "boot the selected Xiaomi system slot (same as bootipq)", "");
