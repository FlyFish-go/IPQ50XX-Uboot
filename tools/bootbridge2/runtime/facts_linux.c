// SPDX-License-Identifier: GPL-2.0-or-later
#include "facts.h"
#include "flash_mtd.h"
#include "sha256.h"
#include "layout.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/klog.h>

static int read_text(const char *path, char *buf, size_t len)
{
	FILE *fp = fopen(path, "rb");
	size_t n;

	if (!fp)
		return -1;
	n = fread(buf, 1, len - 1, fp);
	fclose(fp);
	buf[n] = 0;
	return 0;
}

/* Read the first `len` bytes of a named partition into a new buffer. */
static uint8_t *read_part(const char *name, size_t len)
{
	struct bb_flash f;
	uint8_t *buf;
	int idx = bb_mtd_find(name, 0);

	if (idx < 0 || bb_mtd_open(idx, 0, &f))
		return NULL;
	buf = len <= f.size ? malloc(len) : NULL;
	if (buf && bb_flash_read(&f, 0, buf, len)) {
		free(buf);
		buf = NULL;
	}
	f.close(f.ctx);
	return buf;
}

static void sys_uint(const char *name, const char *attr, unsigned *out)
{
	char path[96], buf[32];
	int idx = bb_mtd_find(name, 0);

	if (idx < 0)
		return;
	snprintf(path, sizeof(path), "/sys/class/mtd/mtd%d/%s", idx, attr);
	if (!read_text(path, buf, sizeof(buf)))
		*out = strtoul(buf, NULL, 0);
}

static void hash_part(const char *name, char out[65])
{
	struct bb_flash f;
	struct bb_sha256 s;
	uint8_t d[32], *buf;
	int idx = bb_mtd_find(name, 0);

	out[0] = 0;
	if (idx < 0 || bb_mtd_open(idx, 0, &f))
		return;
	buf = malloc(f.erase_size);
	if (!buf) {
		f.close(f.ctx);
		return;
	}
	bb_sha256_init(&s);
	for (uint32_t off = 0; off < f.size; off += f.erase_size) {
		if (bb_flash_read(&f, off, buf, f.erase_size)) {
			free(buf);
			f.close(f.ctx);
			return;
		}
		bb_sha256_update(&s, buf, f.erase_size);
	}
	bb_sha256_final(&s, d);
	bb_sha256_hex(d, out);
	free(buf);
	f.close(f.ctx);
}

void bb_facts_collect(struct bb_facts *f)
{
	char model[128];
	uint8_t *buf;
	int n;

	memset(f, 0, sizeof(*f));
	if (!read_text("/proc/device-tree/model", model, sizeof(model)))
		bb_facts_parse_dt_model(f, model);

	if ((buf = read_part("0:CDT", 2048))) {
		bb_facts_parse_cdt(f, buf, 2048);
		free(buf);
	}

	n = klogctl(10, NULL, 0);	/* SYSLOG_ACTION_SIZE_BUFFER */
	if (n > 0 && (buf = malloc(n + 1))) {
		n = klogctl(3, (char *)buf, n);	/* SYSLOG_ACTION_READ_ALL */
		if (n >= 0) {
			buf[n] = 0;
			bb_facts_parse_kmsg(f, (const char *)buf);
		}
		free(buf);
	}
	sys_uint("0:SBL1", "oobsize", &f->mtd_oob);
	sys_uint("0:SBL1", "ecc_strength", &f->mtd_ecc_strength);

	if ((buf = read_part("0:APPSBLENV", 0x40000))) {
		bb_facts_parse_env(f, buf, 0x40000);
		free(buf);
	}
	if ((buf = read_part("0:ART", BB_ART5G_OFFSET + BB_ART5G_BYTES))) {
		bb_facts_parse_art(f, buf, BB_ART5G_OFFSET + BB_ART5G_BYTES);
		free(buf);
	}
	hash_part("0:APPSBL", f->appsbl_sha256[0]);
	hash_part("0:APPSBL_1", f->appsbl_sha256[1]);
	hash_part("0:SBL1", f->sbl1_sha256);
	struct bb_flash slots[2];
	int a = bb_mtd_find("rootfs", 0), b = bb_mtd_find("rootfs_1", 0);
	if (a >= 0 && !bb_mtd_open(a, 0, &slots[0])) {
		if (b >= 0 && !bb_mtd_open(b, 0, &slots[1])) {
			const struct bb_layout *l = bb_layout_slots(&slots[0], &slots[1]);
			if (l) snprintf(f->layout, sizeof(f->layout), "%s", l->id);
			slots[1].close(slots[1].ctx);
		}
		slots[0].close(slots[0].ctx);
	}
}

void bb_evidence_collect_linux(struct bb_evidence *out, unsigned oob, unsigned strength)
{
 static const char *const names[5]={"0:SBL1","0:APPSBL","0:APPSBL_1","0:BOOTCONFIG","0:BOOTCONFIG1"};
 struct bb_flash flash[5]; const struct bb_flash *parts[5]={0};
 memset(flash,0,sizeof(flash)); memset(out,0,sizeof(*out)); out->sampled=1;
 if ((strength!=4 && strength!=8) || !oob) return;
 for (unsigned i=0;i<5;i++) {
  static const uint32_t offsets[5]={0,0x500000,0x640000,0x100000,0x140000};
  int idx=bb_mtd_find(NULL,offsets[i]);
  if (idx<0 || bb_mtd_open(idx,0,&flash[i])) goto done;
  parts[i]=&flash[i];
  struct bb_part_spec spec={.name=names[i]};
  if (!bb_part_name_ok(&spec,flash[i].name)) goto done;
  if (bb_mtd_geometry(idx,parts[i],oob,strength)) goto done;
 }
 bb_evidence_scan(parts,bb_mtd_ecc_stats,out);
done:
 for (unsigned i=0;i<5;i++) if (parts[i]) flash[i].close(flash[i].ctx);
}
