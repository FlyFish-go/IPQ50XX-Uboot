// SPDX-License-Identifier: GPL-2.0-or-later
#include "ipqi_flash.h"
#include "../../bootbridge2/runtime/flash_mtd.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MTD_WRITEABLE_FLAG 0x400

static const char *sim_dir(void)
{
	const char *d = getenv("IPQI_SIM");

	return d && *d ? d : NULL;
}

int ipqi_sim(void)
{
	return sim_dir() != NULL;
}

const char *ipqi_path(const char *p, char *buf, size_t len)
{
	if (!sim_dir())
		return p;
	snprintf(buf, len, "%s/fs%s", sim_dir(), p);
	return buf;
}

static int read_line(const char *path, char *buf, size_t len)
{
	FILE *f = fopen(path, "r");
	size_t n;

	if (!f)
		return -1;
	n = fread(buf, 1, len - 1, f);
	fclose(f);
	buf[n] = 0;
	buf[strcspn(buf, "\n")] = 0;
	return 0;
}

static int sys_u32(int idx, const char *attr, uint32_t *out)
{
	char path[96], buf[32], *end;
	unsigned long v;

	snprintf(path, sizeof(path), "/sys/class/mtd/mtd%d/%s", idx, attr);
	if (read_line(path, buf, sizeof(buf)))
		return -1;
	v = strtoul(buf, &end, 0);
	if (end == buf || v > 0xffffffffUL)
		return -1;
	*out = v;
	return 0;
}

/* ---- simulated NAND ---- */

struct sim_ctx {
	int fd;
	uint32_t base, erase, page;
	uint8_t *programmed;	/* per page, this process only */
	int writable;
};

static int sim_bad(uint32_t abs_off, uint32_t erase)
{
	char path[512], line[64];
	FILE *f;
	int bad = 0;

	snprintf(path, sizeof(path), "%s/bad.txt", sim_dir());
	f = fopen(path, "r");
	if (!f)
		return 0;
	while (fgets(line, sizeof(line), f))
		if (strtoul(line, NULL, 0) / erase == abs_off / erase)
			bad = 1;
	fclose(f);
	return bad;
}

static int s_read(void *ctx, uint32_t off, void *buf, size_t len)
{
	struct sim_ctx *c = ctx;

	return pread(c->fd, buf, len, c->base + off) == (ssize_t)len ? 0 : -EIO;
}

static int s_is_bad(void *ctx, uint32_t off)
{
	struct sim_ctx *c = ctx;

	return sim_bad(c->base + off, c->erase);
}

static int s_erase(void *ctx, uint32_t off)
{
	struct sim_ctx *c = ctx;
	uint8_t *ff;
	int r;

	if (!c->writable)
		return -EROFS;
	ff = malloc(c->erase);
	if (!ff)
		return -ENOMEM;
	memset(ff, 0xff, c->erase);
	r = pwrite(c->fd, ff, c->erase, c->base + off) == (ssize_t)c->erase ? 0 : -EIO;
	free(ff);
	memset(c->programmed + off / c->page, 0, c->erase / c->page);
	return r;
}

static int s_write_page(void *ctx, uint32_t off, const void *buf)
{
	struct sim_ctx *c = ctx;
	uint8_t page[4096];
	const uint8_t *s = buf;

	if (!c->writable)
		return -EROFS;
	if (off % c->page || c->page > sizeof(page) || c->programmed[off / c->page])
		return -EIO;	/* real NAND: no second program without erase */
	if (pread(c->fd, page, c->page, c->base + off) != (ssize_t)c->page)
		return -EIO;
	for (uint32_t i = 0; i < c->page; i++)
		page[i] &= s[i];
	if (pwrite(c->fd, page, c->page, c->base + off) != (ssize_t)c->page)
		return -EIO;
	c->programmed[off / c->page] = 1;
	return 0;
}

static void s_close(void *ctx)
{
	struct sim_ctx *c = ctx;

	close(c->fd);
	free(c->programmed);
	free(c);
}

static int sim_parts(struct ipqi_part_info *out, int max)
{
	char path[512], line[256];
	FILE *f;
	int n = 0;

	snprintf(path, sizeof(path), "%s/parts.txt", sim_dir());
	f = fopen(path, "r");
	if (!f)
		return 0;
	while (n < max && fgets(line, sizeof(line), f)) {
		struct ipqi_part_info *p = &out[n];
		int ro = 0;

		if (sscanf(line, "%31s %i %i %i %i %i", p->name, (int *)&p->offset, (int *)&p->size,
			   (int *)&p->erase_size, (int *)&p->page_size, &ro) != 6)
			continue;
		p->idx = n;
		p->writable = !ro;
		n++;
	}
	fclose(f);
	return n;
}

int ipqi_parts(struct ipqi_part_info *out, int max)
{
	int n = 0;

	if (sim_dir())
		return sim_parts(out, max);
	for (int i = 0; i < 64 && n < max; i++) {
		char path[96], buf[64];
		struct ipqi_part_info *p = &out[n];
		uint32_t flags;

		snprintf(path, sizeof(path), "/sys/class/mtd/mtd%d/type", i);
		if (read_line(path, buf, sizeof(buf)) || strcmp(buf, "nand"))
			continue;
		snprintf(path, sizeof(path), "/sys/class/mtd/mtd%d/name", i);
		if (read_line(path, p->name, sizeof(p->name)) ||
		    sys_u32(i, "offset", &p->offset) || sys_u32(i, "size", &p->size) ||
		    sys_u32(i, "erasesize", &p->erase_size) ||
		    sys_u32(i, "writesize", &p->page_size) || sys_u32(i, "flags", &flags))
			continue;
		p->idx = i;
		p->writable = !!(flags & MTD_WRITEABLE_FLAG);
		n++;
	}
	return n;
}

int ipqi_open(int idx, int writable, struct bb_flash *f)
{
	struct ipqi_part_info parts[IPQI_MAX_PARTS];
	struct sim_ctx *c;
	char path[512];
	int n;

	if (!sim_dir())
		return bb_mtd_open(idx, writable, f);
	n = sim_parts(parts, IPQI_MAX_PARTS);
	if (idx < 0 || idx >= n)
		return -ENOENT;
	if (writable && !parts[idx].writable)
		return -EROFS;
	c = calloc(1, sizeof(*c));
	if (!c)
		return -ENOMEM;
	snprintf(path, sizeof(path), "%s/nand.bin", sim_dir());
	c->fd = open(path, writable ? O_RDWR : O_RDONLY);
	c->programmed = calloc(parts[idx].size / parts[idx].page_size, 1);
	if (c->fd < 0 || !c->programmed) {
		if (c->fd >= 0)
			close(c->fd);
		free(c->programmed);
		free(c);
		return -EIO;
	}
	c->base = parts[idx].offset;
	c->erase = parts[idx].erase_size;
	c->page = parts[idx].page_size;
	c->writable = writable;
	memset(f, 0, sizeof(*f));
	snprintf(f->name, sizeof(f->name), "%s", parts[idx].name);
	f->ctx = c;
	f->offset = parts[idx].offset;
	f->size = parts[idx].size;
	f->erase_size = parts[idx].erase_size;
	f->page_size = parts[idx].page_size;
	f->read = s_read;
	f->is_bad = s_is_bad;
	f->erase = s_erase;
	f->write_page = s_write_page;
	f->close = s_close;
	return 0;
}
