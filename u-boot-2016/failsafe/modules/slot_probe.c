// SPDX-License-Identifier: GPL-2.0
/* Read-only identity of the system in a rootfs slot; same code on every board. */
#include <common.h>
#include <environment.h>
#include <linux/crc32.h>
#include <asm/errno.h>
#include <squashfs_release.h>
#include <slot_probe.h>
#include <failsafe/failsafe.h>

#ifndef CONFIG_CMD_UBI
int slot_probe_env_broken(void) { return 0; }

/* No UBI in this build: nothing can be read from a slot. */
int slot_probe_read(const char *part_name, unsigned long long offset,
		    unsigned long long size, struct slot_probe *p)
{
	memset(p, 0, sizeof(*p));
	strlcpy(p->error, "no_ubi_support", sizeof(p->error));
	return -ENOSYS;
}
#else
#include <ubi_uboot.h>

DECLARE_GLOBAL_DATA_PTR;

extern long long ubi_get_volume_size(char *volume);

#define PROBE_ADDR	0x42000000UL
#define PROBE_MAX	0x02000000U	/* 32 MiB: below the 0x44000000 upload buffer */
#define PROBE_END	(PROBE_ADDR + PROBE_MAX)
/* The top 1 MiB is the SquashFS decode area; the heap is too small on some boards. */
#define PROBE_WORK	(PROBE_END - RT3_SQUASHFS_WORK_MAX)
#define PROBE_IMAGE_MAX	(PROBE_MAX - RT3_SQUASHFS_WORK_MAX)
#define KERNEL_HEAD	0x10000U	/* the kernel image name sits in the first bytes */
#define SB_SIZE		96U
#define SQUASH_MAGIC	0x73717368U

static char *env_snapshot;
static int env_broken;
static ssize_t env_snapshot_len;
static u32 env_snapshot_crc;

/* "ubi part" rewrites mtdids/mtdparts: keep the environment exactly as it was. */
static int env_save(void)
{
	ssize_t len;

	if (env_snapshot)
		return -EBUSY;
	len = hexport_r(&env_htab, '\0', 0, &env_snapshot, 0, 0, NULL);
	if (len <= 0 || !env_snapshot) {
		free(env_snapshot);
		env_snapshot = NULL;
		return -EIO;
	}
	env_snapshot_len = len;
	env_snapshot_crc = crc32(0, (const unsigned char *)env_snapshot, len);
	return 0;
}

static int env_restore(void)
{
	char *verify = NULL;
	ssize_t verify_len;

	if (!env_snapshot || env_snapshot_len <= 0)
		return -EINVAL;
	if (!himport_r(&env_htab, env_snapshot, env_snapshot_len, '\0',
		       0, 0, 0, NULL))
		return -EIO;
	verify_len = hexport_r(&env_htab, '\0', 0, &verify, 0, 0, NULL);
	if (verify_len != env_snapshot_len || !verify ||
	    crc32(0, (const unsigned char *)verify, verify_len) != env_snapshot_crc ||
	    memcmp(verify, env_snapshot, env_snapshot_len)) {
		free(verify);
		return -EIO;
	}
	free(verify);
	free(env_snapshot);
	env_snapshot = NULL;
	env_snapshot_len = 0;
	env_snapshot_crc = 0;
	return 0;
}

static int set_scan_mtd(const char *part_name, unsigned long long offset,
			unsigned long long size)
{
	char mtdparts[112];
	int n;

	if ((strcmp(part_name, "rootfs") && strcmp(part_name, "rootfs_1")) || !size)
		return -EINVAL;
	if (setenv("mtdids", "nand0=nand0"))
		return -EIO;
	n = snprintf(mtdparts, sizeof(mtdparts), "mtdparts=nand0:0x%llx@0x%llx(%s)",
		     (unsigned long long)size, (unsigned long long)offset, part_name);
	if (n < 0 || (size_t)n >= sizeof(mtdparts))
		return -ENOSPC;
	return setenv("mtdparts", mtdparts) ? -EIO : 0;
}

static u32 le32(const u8 *p)
{
	return p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) | ((u32)p[3] << 24);
}

static int squashfs_used(const u8 *sb, u64 volume_size, u64 *used)
{
	if (le32(sb) != SQUASH_MAGIC)
		return -EINVAL;
	*used = le32(sb + 40) | ((u64)le32(sb + 44) << 32);
	if (le32(sb + 12) < 4096 || le32(sb + 12) > 1048576 ||
	    sb[28] != 4 || sb[30] != 0 || *used < SB_SIZE ||
	    *used > PROBE_IMAGE_MAX || *used > volume_size)
		return -EFBIG;
	return 0;
}

static void probe_kernel(struct ubi_volume *v, struct slot_probe *p)
{
	long long vsize = ubi_get_volume_size(v->name);
	size_t n;

	if (p->kernel[0] || vsize <= 0)
		return;
	n = vsize < KERNEL_HEAD ? (size_t)vsize : KERNEL_HEAD;
	if (ubi_volume_read(v->name, (char *)PROBE_ADDR, n))
		return;
	slot_probe_kernel_version((const u8 *)PROBE_ADDR, n, p->kernel,
				  sizeof(p->kernel));
}

/* rootfs (OpenWrt) or ubi_rootfs (QSDK); other volumes such as wifi_fw may
 * also hold SquashFS and are not the system. A read or format problem is
 * reported in p->error; a SquashFS without a release file is not an error. */
static void probe_rootfs(struct ubi_volume *v, struct slot_probe *p)
{
	long long vsize = ubi_get_volume_size(v->name);
	const char *err = NULL;
	u64 used;
	int r;

	if (p->system[0] || p->error[0] || vsize <= 0)
		return;
	if (vsize < SB_SIZE || ubi_volume_read(v->name, (char *)PROBE_ADDR, SB_SIZE)) {
		err = "rootfs_read_failed";
	} else {
		r = squashfs_used((const u8 *)PROBE_ADDR, (u64)vsize, &used);
		if (r == -EINVAL)
			return;		/* not SquashFS */
		if (r)
			err = "rootfs_too_large_or_invalid";
		else if (ubi_volume_read(v->name, (char *)PROBE_ADDR, (size_t)used))
			err = "rootfs_read_failed";
		else {
			r = rt3_squashfs_read_release_ws((const void *)PROBE_ADDR,
							 (size_t)used, p->system,
							 sizeof(p->system),
							 (void *)PROBE_WORK,
							 RT3_SQUASHFS_WORK_MAX);
			if (r) {
				p->system[0] = 0;
				if (r != -ENOENT)
					err = "release_file_unreadable";
			}
		}
	}
	if (err)
		strlcpy(p->error, err, sizeof(p->error));
}

int slot_probe_read(const char *part_name, unsigned long long offset,
		    unsigned long long size,
		    struct slot_probe *p)
{
	struct ubi_device *ubi;
	struct ubi_volume *v;
	int i, ret;

	memset(p, 0, sizeof(*p));
	if (env_broken) {
		p->env_lost = 1;
		strlcpy(p->error, "environment_restore_failed", sizeof(p->error));
		return -EIO;
	}
	/* The probe window is also part of the /upload buffer on some boards:
	 * an upload validated earlier must not be written after this. */
	failsafe_upload_invalidate();
	if (CONFIG_SYS_SDRAM_BASE > PROBE_ADDR ||
	    PROBE_END - CONFIG_SYS_SDRAM_BASE > gd->ram_size) {
		strlcpy(p->error, "probe_buffer_out_of_ram", sizeof(p->error));
		return -ERANGE;
	}
	ret = env_save();
	if (ret) {
		strlcpy(p->error, "environment_save_failed", sizeof(p->error));
		return ret;
	}
	ret = set_scan_mtd(part_name, offset, size);
	if (!ret) {
		/* Detach even after a failed attach, as the H3C scan always did. */
		if (ubi_part_readonly((char *)part_name, NULL) || !ubi_devices[0]) {
			ret = -ENODEV;
		} else {
			ubi = ubi_devices[0];
			for (i = 0; i < ubi->vtbl_slots + 1; i++) {
				v = ubi->volumes[i];
				if (!v)
					continue;
				if (!strcmp(v->name, "kernel"))
					probe_kernel(v, p);
				else if (!strcmp(v->name, "rootfs") ||
					 !strcmp(v->name, "ubi_rootfs"))
					probe_rootfs(v, p);
			}
		}
		ubi_exit_readonly();
	}
	if (ret)
		strlcpy(p->error, ret == -ENODEV ? "no_ubi" : "scan_setup_failed",
			sizeof(p->error));
	if (env_restore()) {
		env_broken = 1;
		p->env_lost = 1;
		strlcpy(p->error, "environment_restore_failed", sizeof(p->error));
		return -EIO;
	}
	return ret;
}
int slot_probe_env_broken(void)
{
	return env_broken;
}
#endif /* CONFIG_CMD_UBI */
