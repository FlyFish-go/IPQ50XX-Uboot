/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Files appended to the installer binary by mkpkg.py:
 *   [ELF][entry data...][table: n x entry][trailer]
 * entry   = char name[48]; u32 offset; u32 length; u8 sha256[32]   (88 bytes)
 * trailer = "IPQIPKG1"; u32 count; u32 table_offset; char version[48] (64 bytes)
 * Offsets are from the start of the file, integers little endian. */
#ifndef IPQI_PAYLOAD_H
#define IPQI_PAYLOAD_H

#include <stddef.h>
#include <stdint.h>

#define IPQI_PKG_MAGIC "IPQIPKG1"

/* Load and SHA-256 check one entry of our own executable. Returns malloc'd
 * bytes or NULL (with a reason in err). */
uint8_t *ipqi_payload(const char *name, size_t *len, char *err, size_t errlen);
const char *ipqi_pkg_version(void);
void ipqi_sha256(const void *data, size_t len, uint8_t out[32]);

#endif
