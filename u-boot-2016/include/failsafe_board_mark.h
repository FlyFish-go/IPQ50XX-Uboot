/* SPDX-License-Identifier: GPL-2.0+ */
/*
 * Board mark of a non-H3C U-Boot image.
 *
 * Every non-H3C build carries exactly one "IPQ50XX-UBOOT-BOARD=<id>\0" string
 * (<id> = the defconfig name, CONFIG_FAILSAFE_BOARD_ID). The web U-Boot update
 * installs an ELF only when it holds exactly one mark and that mark names the
 * running board, so another board's U-Boot (or an older build without a mark)
 * is refused before anything is written.
 *
 * Pure logic, no U-Boot dependencies, host tested.
 */
#ifndef FAILSAFE_BOARD_MARK_H
#define FAILSAFE_BOARD_MARK_H

#ifdef __UBOOT__
#include <common.h>
#else
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#endif

#define FAILSAFE_BOARD_MARK_PREFIX	"IPQ50XX-UBOOT-BOARD="
#define FAILSAFE_BOARD_MARK_ID_MAX	48

#define FAILSAFE_BOARD_MARK_OK		0
#define FAILSAFE_BOARD_MARK_UNSET	(-1)	/* this build has no valid id */
#define FAILSAFE_BOARD_MARK_MISSING	(-2)	/* image has no mark */
#define FAILSAFE_BOARD_MARK_MULTIPLE	(-3)	/* image has more than one mark */
#define FAILSAFE_BOARD_MARK_BAD		(-4)	/* mark not terminated or bad id */
#define FAILSAFE_BOARD_MARK_MISMATCH	(-5)	/* mark names another board */

/* Ids are short, [a-z0-9_] only, so they can go into JSON unescaped. */
static inline size_t failsafe_board_mark_id_len(const uint8_t *s, size_t avail)
{
	size_t i;

	for (i = 0; i < avail && i <= FAILSAFE_BOARD_MARK_ID_MAX; i++) {
		uint8_t c = s[i];

		if (!c)
			return i ? i : (size_t)-1;
		if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_'))
			return (size_t)-1;
	}
	return (size_t)-1;	/* too long or not terminated inside the image */
}

/*
 * Check img[0..n) against own_id. prefix/plen is the mark prefix; the caller
 * passes it from its own mark object so the running image holds the prefix
 * only once. found (found_sz > FAILSAFE_BOARD_MARK_ID_MAX) receives the id
 * read from the image on OK and MISMATCH, "" otherwise.
 */
static inline int failsafe_board_mark_check(const uint8_t *img, size_t n,
		const char *prefix, size_t plen, const char *own_id,
		char *found, size_t found_sz)
{
	size_t own_len, i, hit = (size_t)-1, count = 0, id_len;

	if (found && found_sz)
		found[0] = '\0';
	if (!prefix || !plen || !own_id || !found ||
	    found_sz <= FAILSAFE_BOARD_MARK_ID_MAX)
		return FAILSAFE_BOARD_MARK_UNSET;
	own_len = failsafe_board_mark_id_len((const uint8_t *)own_id,
					     FAILSAFE_BOARD_MARK_ID_MAX + 1);
	if (own_len == (size_t)-1)
		return FAILSAFE_BOARD_MARK_UNSET;
	if (!img || n < plen)
		return FAILSAFE_BOARD_MARK_MISSING;
	for (i = 0; i + plen <= n; i++) {
		if (img[i] == (uint8_t)prefix[0] && !memcmp(img + i, prefix, plen)) {
			if (++count > 1)
				return FAILSAFE_BOARD_MARK_MULTIPLE;
			hit = i;
		}
	}
	if (!count)
		return FAILSAFE_BOARD_MARK_MISSING;
	id_len = failsafe_board_mark_id_len(img + hit + plen, n - hit - plen);
	if (id_len == (size_t)-1)
		return FAILSAFE_BOARD_MARK_BAD;
	memcpy(found, img + hit + plen, id_len);
	found[id_len] = '\0';
	if (id_len != own_len || memcmp(found, own_id, own_len))
		return FAILSAFE_BOARD_MARK_MISMATCH;
	return FAILSAFE_BOARD_MARK_OK;
}

#endif
