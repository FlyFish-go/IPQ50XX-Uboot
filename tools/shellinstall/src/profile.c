// SPDX-License-Identifier: GPL-2.0-or-later
#include "profile.h"

#include <stddef.h>

#define N(a) (sizeof(a) / sizeof((a)[0]))

/* CMCC MR3000D-CI: TTL recon 2026-11-12, U-Boot smeminfo == Linux ofpart.
 * Stock fw OpenWrt CC "CMIOT-SR1.0.1", DT config mp03.3-m1. */
static const struct ipqi_layout_part mr3000d_ci_layout[] = {
	{ "0:SBL1",        0x0000000, 0x0080000 },
	{ "0:MIBIB",       0x0080000, 0x0080000 },
	{ "0:BOOTCONFIG",  0x0100000, 0x0040000 },
	{ "0:BOOTCONFIG1", 0x0140000, 0x0040000 },
	{ "0:QSEE",        0x0180000, 0x0100000 },
	{ "0:QSEE_1",      0x0280000, 0x0100000 },
	{ "0:DEVCFG",      0x0380000, 0x0040000 },
	{ "0:DEVCFG_1",    0x03c0000, 0x0040000 },
	{ "0:CDT",         0x0400000, 0x0040000 },
	{ "0:CDT_1",       0x0440000, 0x0040000 },
	{ "0:APPSBLENV",   0x0480000, 0x0080000 },
	{ "0:APPSBL",      0x0500000, 0x0140000 },
	{ "0:APPSBL_1",    0x0640000, 0x0140000 },
	{ "0:ART",         0x0780000, 0x0100000 },
	{ "0:TRAINING",    0x0880000, 0x0080000 },
	{ "rootfs",        0x0900000, 0x3a00000 },
	{ "rootfs_1",      0x4300000, 0x3a00000 },
};

static const char *const boot_area[] = {
	"0:SBL1", "0:MIBIB", "0:BOOTCONFIG", "0:BOOTCONFIG1", "0:QSEE", "0:QSEE_1",
	"0:DEVCFG", "0:DEVCFG_1", "0:CDT", "0:CDT_1", "0:APPSBLENV", "0:APPSBL",
	"0:APPSBL_1", "0:ART", "0:TRAINING", NULL,
};

/* Ruijie RG-MA3063 (CMCC edition, project wuhu-cmcc-main): TTL recon
 * 2026-11-12, U-Boot smeminfo == Linux ofpart. Stock fw MA_2.1(1)B6,
 * DT config mp02.1 (shared with other IPQ5000 boards, so the marker decides).
 * QSEE_1/DEVCFG_1/CDT_1 are erased on this model; only APPSBL is a real pair. */
static const struct ipqi_layout_part ma3063_layout[] = {
	{ "0:SBL1",        0x0000000, 0x0080000 },
	{ "0:MIBIB",       0x0080000, 0x0080000 },
	{ "0:BOOTCONFIG",  0x0100000, 0x0040000 },
	{ "0:BOOTCONFIG1", 0x0140000, 0x0040000 },
	{ "0:QSEE",        0x0180000, 0x0100000 },
	{ "0:QSEE_1",      0x0280000, 0x0100000 },
	{ "0:DEVCFG",      0x0380000, 0x0040000 },
	{ "0:DEVCFG_1",    0x03c0000, 0x0040000 },
	{ "0:CDT",         0x0400000, 0x0040000 },
	{ "0:CDT_1",       0x0440000, 0x0040000 },
	{ "0:APPSBLENV",   0x0480000, 0x0080000 },
	{ "0:APPSBL",      0x0500000, 0x0140000 },
	{ "0:APPSBL_1",    0x0640000, 0x0140000 },
	{ "0:ART",         0x0780000, 0x0100000 },
	{ "0:TRAINING",    0x0880000, 0x0080000 },
	{ "rootfs",        0x0900000, 0x3200000 },
	{ "rootfs_1",      0x3b00000, 0x3200000 },
	{ "ttyMTD",        0x6d00000, 0x0120000 },
	{ "productinfo",   0x6e20000, 0x0080000 },
	{ "data",          0x6ea0000, 0x1040000 },
};

/* productinfo holds this unit's SN and MACs: keep it with the boot area. */
static const char *const ma3063_backup[] = {
	"0:SBL1", "0:MIBIB", "0:BOOTCONFIG", "0:BOOTCONFIG1", "0:QSEE", "0:QSEE_1",
	"0:DEVCFG", "0:DEVCFG_1", "0:CDT", "0:CDT_1", "0:APPSBLENV", "0:APPSBL",
	"0:APPSBL_1", "0:ART", "0:TRAINING", "productinfo", NULL,
};

const struct ipqi_profile ipqi_profiles[] = {
	{
		.id = "cmcc-mr3000d-ci",
		.title = "中国移动 MR3000D-CI",
		.dt_model = "IPQ5018/AP-MP03.3-M1",
		.marker_file = "/etc/openwrt_release",
		.marker_text = "CMIOT-SR",
		.erase_size = 0x20000,
		.page_size = 0x800,
		.layout = mr3000d_ci_layout,
		.layout_len = N(mr3000d_ci_layout),
		.backup = boot_area,
		.slots = IPQI_SLOTS_BOOTCONFIG,
		.payload = "uboot/cmcc-mr3000d-ci.mbn",
	},
	{
		.id = "ruijie-rg-ma3063",
		.title = "锐捷 RG-MA3063",
		.dt_model = "IPQ5018/AP-MP02.1",
		.marker_file = "/etc/rj_issus",
		.marker_text = "RG-MA3063-",
		.erase_size = 0x20000,
		.page_size = 0x800,
		.layout = ma3063_layout,
		.layout_len = N(ma3063_layout),
		.backup = ma3063_backup,
		.slots = IPQI_SLOTS_BOOTCONFIG,
		.payload = "uboot/ruijie-rg-ma3063.mbn",
	},
};

const unsigned ipqi_profiles_len = N(ipqi_profiles);
