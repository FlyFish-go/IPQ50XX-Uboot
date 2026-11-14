/* SPDX-License-Identifier: GPL-2.0+ */
#ifndef __SQUASHFS_RELEASE_H__
#define __SQUASHFS_RELEASE_H__
#include <stddef.h>
/* Returns 0 with a 1..96 printable ASCII release string, else negative errno.
 * Reads only regular allowlisted /etc release files; never follows symlinks.
 */
int rt3_squashfs_read_release(const void *image, size_t image_len,
                              char *out, size_t out_len);
/* Same, decoding into a caller work area instead of the heap; the work area
 * must hold one SquashFS block (at most RT3_SQUASHFS_WORK_MAX bytes). */
#define RT3_SQUASHFS_WORK_MAX (1U << 20)
int rt3_squashfs_read_release_ws(const void *image, size_t image_len,
                                 char *out, size_t out_len,
                                 void *work, size_t work_len);
#endif
