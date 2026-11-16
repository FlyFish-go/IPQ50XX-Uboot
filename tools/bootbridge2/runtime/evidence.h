/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef BB_EVIDENCE_H
#define BB_EVIDENCE_H
#include "flash.h"
#include <stdint.h>
#define BB_EVIDENCE_PARTS 5
#define BB_EVIDENCE_CORRECTED_MAX 8U
struct bb_evidence_part { uint32_t failed, corrected, non_ff; int read_ok, header_ok; };
struct bb_evidence { int sampled, ok; struct bb_evidence_part part[BB_EVIDENCE_PARTS]; };
typedef int (*bb_evidence_stats_fn)(void *ctx, uint32_t *failed, uint32_t *corrected);
/* Whole partitions in SBL1, APPSBL, APPSBL_1, BOOTCONFIG, BOOTCONFIG1 order. */
int bb_evidence_scan(const struct bb_flash *parts[BB_EVIDENCE_PARTS],
                     bb_evidence_stats_fn stats, struct bb_evidence *out);
void bb_evidence_collect_linux(struct bb_evidence *out, unsigned expected_oob, unsigned strength);
#endif
