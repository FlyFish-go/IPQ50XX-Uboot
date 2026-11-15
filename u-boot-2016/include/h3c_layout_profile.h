/* SPDX-License-Identifier: GPL-2.0+ */
/*
 * The OEM NAND partition scheme an H3C build accepts. The boot prefix
 * (SBL1 .. TRAINING) and the first rootfs at 0x900000 are the same on every
 * supported model; the rootfs slot size and the OEM data partitions behind
 * the two slots differ per model.
 */
#ifndef __H3C_LAYOUT_PROFILE_H__
#define __H3C_LAYOUT_PROFILE_H__

#ifdef CONFIG_H3C_LAYOUT_NX54
/* NX54: two 45.25 MiB rootfs slots, then pdt_data, pdt_data_1 and exp.
 * There is no plugin partition and no single-rootfs layout. */
#define H3C_LAYOUT_DUAL_SIZE 0x02d40000ULL
#define H3C_LAYOUT_SINGLE_SIZE 0ULL
#define H3C_LAYOUT_SINGLE_XL_SIZE 0ULL
#define H3C_LAYOUT_SINGLE_SIZE_OK(s) 0
#define H3C_LAYOUT_SUFFIX_COUNT 3U
#define H3C_LAYOUT_SUFFIX_PARTS \
	{ "pdt_data",   0x06380000ULL, 0x00900000ULL }, \
	{ "pdt_data_1", 0x06c80000ULL, 0x00900000ULL }, \
	{ "exp",        0x07580000ULL, 0x00100000ULL }
#define H3C_LAYOUT_OEMDATA_NAMES "smem_pdt_data.bin, smem_pdt_data_1.bin or smem_exp.bin"
#else
/* NX30 family: two 40 MiB rootfs slots, then pdt_data, pdt_data_1, exp
 * and plugin; or one 80 MiB rootfs, or the extra-large single rootfs that
 * runs from 0x900000 to the end of the OEM data partitions (0x7d00000). */
#define H3C_LAYOUT_DUAL_SIZE 0x02800000ULL
#define H3C_LAYOUT_SINGLE_SIZE 0x05000000ULL
#define H3C_LAYOUT_SINGLE_XL_SIZE 0x07400000ULL
#define H3C_LAYOUT_SINGLE_SIZE_OK(s) \
	((s) == H3C_LAYOUT_SINGLE_SIZE || (s) == H3C_LAYOUT_SINGLE_XL_SIZE)
#define H3C_LAYOUT_SUFFIX_COUNT 4U
#define H3C_LAYOUT_SUFFIX_PARTS \
	{ "pdt_data",   0x05900000ULL, 0x00600000ULL }, \
	{ "pdt_data_1", 0x05f00000ULL, 0x00600000ULL }, \
	{ "exp",        0x06500000ULL, 0x00100000ULL }, \
	{ "plugin",     0x06600000ULL, 0x01700000ULL }
#define H3C_LAYOUT_OEMDATA_NAMES "smem_pdt_data.bin, smem_pdt_data_1.bin, smem_exp.bin or smem_plugin.bin"
#endif

#endif /* __H3C_LAYOUT_PROFILE_H__ */
