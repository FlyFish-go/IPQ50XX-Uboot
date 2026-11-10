// SPDX-License-Identifier: GPL-2.0+
/* Build identity: board, NAND profile, source mask and ECC of this U-Boot.
 * The rescue page accepts a U-Boot candidate only when it carries exactly one
 * identity string equal to the running build's, so a build for another board
 * or another NAND profile is refused before anything is erased.
 */
#ifdef H3C_BUILD_ID_HOST_TEST
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;
#else
#include <common.h>
#include <asm/errno.h>
#include <h3c_build_id.h>
#endif
#if defined(CONFIG_H3C_NAND_AUTO_PROFILE) || defined(CONFIG_H3C_NAND_ACCEPT_AUTO_IMAGE)
#include <h3c_nand_catalog.h>
#endif
#ifdef CONFIG_H3C_NAND_AUTO_PROFILE
#include <h3c_nand_auto.h>
#endif

#define H3C_ID_STR2(x) #x
#define H3C_ID_STR(x) H3C_ID_STR2(x)

#if defined(CONFIG_TARGET_IPQ5018_H3C_HW_A)
#define H3C_ID_BOARD "A"
#elif defined(CONFIG_TARGET_IPQ5018_H3C_HW_C)
#define H3C_ID_BOARD "C"
#elif defined(CONFIG_TARGET_IPQ5018_H3C_HW_D)
#define H3C_ID_BOARD "D"
#elif defined(CONFIG_TARGET_IPQ5018_H3C_RT3000_B)
#define H3C_ID_BOARD "B"
#else
#define H3C_ID_BOARD "unknown"
#endif

#ifdef CONFIG_H3C_NAND_AUTO_PROFILE
/* The NAND profile is selected at run time; see h3c_build_profile(). */
#define H3C_ID_PROFILE "auto"
#elif defined(CONFIG_H3C_NAND_PROFILE_ID)
#define H3C_ID_PROFILE CONFIG_H3C_NAND_PROFILE_ID
#else
#define H3C_ID_PROFILE ""
#endif
#ifdef CONFIG_H3C_NAND_SOURCE_MASK
#define H3C_ID_MASK H3C_ID_STR(CONFIG_H3C_NAND_SOURCE_MASK)
#else
#define H3C_ID_MASK "none"
#endif
#ifdef CONFIG_H3C_NAND_LOAD_ECC_BITS
#define H3C_ID_ECC H3C_ID_STR(CONFIG_H3C_NAND_LOAD_ECC_BITS)
#else
#define H3C_ID_ECC "none"
#endif

static const char h3c_build_id_string[] __attribute__((used)) =
	"H3C-UBOOT-ID:v1;board=" H3C_ID_BOARD ";profile=" H3C_ID_PROFILE
	";mask=" H3C_ID_MASK ";ecc=" H3C_ID_ECC ";";

/* The search key, each byte + 1, so this file is not itself a match. */
static const volatile char h3c_build_id_key[] = "I4D.VCPPU.JE;w2<";

const char *h3c_build_id(void)
{
	return h3c_build_id_string;
}

/* Pieces of the identity for the rescue page (which package folder fits). */
const char *h3c_build_board(void) { return H3C_ID_BOARD; }
#ifdef CONFIG_H3C_NAND_AUTO_PROFILE
/* An auto build reports what it detected, "" / "none" if nothing. */
const char *h3c_build_profile(void)
{
	const struct h3c_nand_catalog_profile *row = h3c_nand_auto_row();

	return row ? row->profile_id : "";
}

const char *h3c_build_load_ecc(void)
{
	unsigned int mode = h3c_nand_auto_mode();

	return mode == 4U ? "4" : mode == 8U ? "8" : "none";
}
#else
const char *h3c_build_profile(void) { return H3C_ID_PROFILE; }
const char *h3c_build_load_ecc(void) { return H3C_ID_ECC; }
#endif

#if defined(CONFIG_H3C_NAND_AUTO_PROFILE) || defined(CONFIG_H3C_NAND_ACCEPT_AUTO_IMAGE)
struct h3c_id_fields {
	char board[8], profile[64], mask[16], ecc[8];
};

/* Consume "key" + value up to ';' (value copied to out). */
static int h3c_id_field(const char **p, const char *key, char *out, size_t cap)
{
	size_t k = strlen(key), n = 0;

	if (strncmp(*p, key, k))
		return -1;
	*p += k;
	while (**p && **p != ';') {
		if (n + 1 >= cap)
			return -1;
		out[n++] = *(*p)++;
	}
	if (**p != ';')
		return -1;
	(*p)++;
	out[n] = '\0';
	return 0;
}

/* Parse "H3C-UBOOT-ID:v1;board=..;profile=..;mask=..;ecc=..;" exactly. */
static int h3c_id_parse(const char *s, size_t avail, struct h3c_id_fields *f)
{
	static const char prefix[] = "H3C-UBOOT-ID:v1;";

	if (!memchr(s, 0, avail) || strncmp(s, prefix, sizeof(prefix) - 1))
		return -1;
	s += sizeof(prefix) - 1;
	if (h3c_id_field(&s, "board=", f->board, sizeof(f->board)) ||
	    h3c_id_field(&s, "profile=", f->profile, sizeof(f->profile)) ||
	    h3c_id_field(&s, "mask=", f->mask, sizeof(f->mask)) ||
	    h3c_id_field(&s, "ecc=", f->ecc, sizeof(f->ecc)))
		return -1;
	return *s ? -1 : 0;
}

#ifdef CONFIG_H3C_NAND_AUTO_PROFILE
/* A pinned candidate fits this auto build only if its row and ECC are the
 * ones detected on this device and its source mask is admitted by the row
 * for that ECC (so the pinned image will accept the NAND at boot). */
static int h3c_id_pinned_matches_detected(const struct h3c_id_fields *f)
{
	const struct h3c_nand_catalog_profile *row = h3c_nand_auto_row();
	unsigned int mode = h3c_nand_auto_mode(), mask = 0, i;
	const char *m = f->mask;

	if (!row || (mode != 4U && mode != 8U) || strcmp(f->profile, row->profile_id) ||
	    f->ecc[0] != (char)('0' + mode) || f->ecc[1])
		return 0;
	if (m[0] != '0' || m[1] != 'x' || !m[2])
		return 0;
	for (i = 2; m[i]; i++) {
		char c = m[i];
		unsigned int d;

		d = c >= '0' && c <= '9' ? (unsigned int)(c - '0') :
		    c >= 'a' && c <= 'f' ? (unsigned int)(c - 'a' + 10) : 16U;
		if (d > 15U || mask > 0xfffffffU)
			return 0;
		mask = mask << 4 | d;
	}
	if (!mask || (mask & (mask - 1U)) ||
	    !(row->appsbl_source_mask & mask) ||
	    !((mode == 4U ? row->appsbl_ecc4_source_mask :
			    row->appsbl_ecc8_source_mask) & mask))
		return 0;
	return 1;
}
#endif

/* Identities that differ from this build's but are still acceptable:
 * the same board and an auto image, and (auto build only) a pinned image
 * for exactly the profile and ECC detected on this device. */
static int h3c_id_compatible(const char *cand, size_t avail)
{
	struct h3c_id_fields f;

	if (h3c_id_parse(cand, avail, &f) || strcmp(f.board, H3C_ID_BOARD))
		return 0;
	if (!strcmp(f.profile, "auto"))
		return !strcmp(f.mask, "none") && !strcmp(f.ecc, "none");
#ifdef CONFIG_H3C_NAND_AUTO_PROFILE
	return h3c_id_pinned_matches_detected(&f);
#else
	return 0;
#endif
}
#endif

int h3c_build_id_check(const u8 *image, size_t size)
{
	char key[sizeof(h3c_build_id_key)];
	size_t i, key_len = sizeof(key) - 1;
	size_t own_len = strlen(h3c_build_id_string);
	unsigned int found = 0;
	int match = 0;
	size_t pos = 0;

	if (!image)
		return -EINVAL;
	for (i = 0; i < key_len; i++)
		key[i] = h3c_build_id_key[i] - 1;
	key[key_len] = '\0';
	for (i = 0; i + key_len <= size; i++) {
		if (memcmp(image + i, key, key_len))
			continue;
		found++;
		pos = i;
		/* Compare the terminating NUL too: a longer identity is different. */
		match = size - i > own_len &&
			!memcmp(image + i, h3c_build_id_string, own_len + 1);
	}
	if (!found)
		return -ENOENT;
	if (found != 1)
		return -EEXIST;
#if defined(CONFIG_H3C_NAND_AUTO_PROFILE) || defined(CONFIG_H3C_NAND_ACCEPT_AUTO_IMAGE)
	if (!match && h3c_id_compatible((const char *)image + pos, size - pos))
		match = 1;
#else
	(void)pos;
#endif
	return match ? 0 : -EXDEV;
}
