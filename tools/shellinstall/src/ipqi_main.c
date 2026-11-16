// SPDX-License-Identifier: GPL-2.0-or-later
/* IPQ50XX-Uboot system installer, stage 2: a small web page served from the
 * stock firmware. Checks the unit against a model profile, makes a backup the
 * user must download, then writes both APPSBL copies and reads them back.
 *
 *   ipqi serve [-p port] [-d workdir]
 *   ipqi check            print the checks as JSON and exit */
#include "ipqi_flash.h"
#include "payload.h"
#include "profile.h"
#include "../../bootbridge2/runtime/backup.h"
#include "../../bootbridge2/runtime/bootconfig.h"
#include "../../bootbridge2/runtime/sha256.h"
#include "www_index.h"

#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/reboot.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>

enum { C_MODEL, C_LAYOUT, C_SECURE, C_WRITABLE, C_BAD, C_READ, C_SLOT, C_PAYLOAD, C_COUNT };

static const char *const check_label[C_COUNT] = {
	"机型", "分区表", "安全启动", "U-Boot 分区可写", "U-Boot 分区没有坏块",
	"现有 U-Boot 能完整读出", "启动选择记录", "安装包里的 U-Boot",
};

struct check {
	int ok;
	char detail[256];
};

static struct {
	const char *dir;
	const struct ipqi_profile *prof;
	struct check c[C_COUNT];
	int idx_appsbl[2];		/* [0] lower offset, [1] higher */
	int active;			/* 0/1 = lower/higher copy boots */
	uint8_t *payload;
	size_t payload_len;
	int backup_ready, backup_downloaded;
	struct bb_backup_result backup;
	int installed;
	char action[16], code[32], message[512];
} S = { .dir = "/tmp/ipqi", .idx_appsbl = { -1, -1 }, .active = -1 };

static void set_result(const char *action, const char *code, const char *fmt, ...)
{
	va_list ap;

	snprintf(S.action, sizeof(S.action), "%s", action);
	snprintf(S.code, sizeof(S.code), "%s", code);
	va_start(ap, fmt);
	vsnprintf(S.message, sizeof(S.message), fmt, ap);
	va_end(ap);
}

static void fail(int k, const char *fmt, ...)
{
	va_list ap;

	S.c[k].ok = 0;
	va_start(ap, fmt);
	vsnprintf(S.c[k].detail, sizeof(S.c[k].detail), fmt, ap);
	va_end(ap);
}

static void pass(int k, const char *fmt, ...)
{
	va_list ap;

	S.c[k].ok = 1;
	va_start(ap, fmt);
	vsnprintf(S.c[k].detail, sizeof(S.c[k].detail), fmt, ap);
	va_end(ap);
}

static int read_file(const char *path, char *buf, size_t len)
{
	char p[512];
	FILE *f = fopen(ipqi_path(path, p, sizeof(p)), "rb");
	size_t n;

	if (!f)
		return -1;
	n = fread(buf, 1, len - 1, f);
	fclose(f);
	buf[n] = 0;
	return 0;
}

static void hex(const uint8_t *s, size_t n, char *out)
{
	for (size_t i = 0; i < n; i++)
		sprintf(out + 2 * i, "%02x", s[i]);
}

static const struct ipqi_part_info *find_off(const struct ipqi_part_info *p, int n, uint32_t off)
{
	for (int i = 0; i < n; i++)
		if (p[i].offset == off)
			return &p[i];
	return NULL;
}

static const struct ipqi_part_info *find_name(const struct ipqi_part_info *p, int n, const char *name)
{
	for (int i = 0; i < n; i++)
		if (!strcmp(p[i].name, name))
			return &p[i];
	return NULL;
}

static int ready(void)
{
	for (int k = 0; k < C_COUNT; k++)
		if (!S.c[k].ok)
			return 0;
	return 1;
}

/* Padded image the APPSBL copies must hold after installing. */
static uint8_t *image_for(uint32_t size)
{
	uint8_t *img = malloc(size);

	if (!img)
		return NULL;
	memset(img, 0xff, size);
	memcpy(img, S.payload, S.payload_len);
	return img;
}

static void run_checks(void)
{
	struct ipqi_part_info parts[IPQI_MAX_PARTS];
	char model[256] = "", marker[4096] = "", buf[64];
	const struct ipqi_layout_part *ap[2] = { NULL, NULL };
	int n, k;

	memset(S.c, 0, sizeof(S.c));
	for (k = 0; k < C_COUNT; k++)
		fail(k, "前面的检查没有通过，未检查");
	S.prof = NULL;
	S.active = -1;
	S.idx_appsbl[0] = S.idx_appsbl[1] = -1;

	/* 1. Which model: device tree model plus an OEM firmware marker. */
	read_file("/proc/device-tree/model", model, sizeof(model));
	for (unsigned i = 0; i < ipqi_profiles_len && !S.prof; i++) {
		const struct ipqi_profile *p = &ipqi_profiles[i];

		if (strstr(model, p->dt_model) && !read_file(p->marker_file, marker, sizeof(marker)) &&
		    strstr(marker, p->marker_text))
			S.prof = p;
	}
	if (!S.prof) {
		fail(C_MODEL, "不认识这台机器（设备树：%s）。本安装包只支持已验证的机型。",
		     model[0] ? model : "读不到");
		return;
	}
	pass(C_MODEL, "%s（%s）", S.prof->title, model);

	/* 2. Partition table: every entry of the profile, exact name/offset/size. */
	n = ipqi_parts(parts, IPQI_MAX_PARTS);
	for (unsigned i = 0; i < S.prof->layout_len; i++) {
		const struct ipqi_layout_part *l = &S.prof->layout[i];
		const struct ipqi_part_info *p = find_off(parts, n, l->offset);

		if (!strcmp(l->name, "0:APPSBL"))
			ap[0] = l;
		if (!strcmp(l->name, "0:APPSBL_1"))
			ap[1] = l;
		/* SBL swaps the names of a failsafe pair (X <-> X_1) when its
		 * selector is 1, so the pair partner's name is accepted too. */
		if (!p || p->size != l->size || p->erase_size != S.prof->erase_size ||
		    p->page_size != S.prof->page_size) {
			fail(C_LAYOUT, "分区 %s（偏移 0x%x，大小 0x%x）和机型资料对不上", l->name,
			     l->offset, l->size);
			return;
		}
		size_t ln = strlen(l->name), pn = strlen(p->name);
		int same = !strcmp(p->name, l->name) ||
			   (pn == ln + 2 && !strncmp(p->name, l->name, ln) && !strcmp(p->name + ln, "_1")) ||
			   (ln == pn + 2 && !strncmp(l->name, p->name, pn) && !strcmp(l->name + pn, "_1"));
		if (!same) {
			fail(C_LAYOUT, "偏移 0x%x 处的分区叫 %s，应为 %s", l->offset, p->name, l->name);
			return;
		}
	}
	if (!ap[0] || (S.prof->slots == IPQI_SLOTS_BOOTCONFIG && !ap[1])) {
		fail(C_LAYOUT, "机型资料里没有 U-Boot 分区");
		return;
	}
	pass(C_LAYOUT, "%u 个分区的名字、偏移、大小都和机型资料一致", S.prof->layout_len);

	/* 3. Secure boot must be off, or our unsigned U-Boot will not start. */
	if (read_file("/sys/devices/system/qfprom/qfprom0/authenticate", buf, sizeof(buf))) {
		fail(C_SECURE, "读不到 /sys/devices/system/qfprom/qfprom0/authenticate，无法确认");
		return;
	}
	if (buf[0] != '0') {
		fail(C_SECURE, "安全启动已开启（authenticate=%c），装了也启动不了", buf[0]);
		return;
	}
	pass(C_SECURE, "未开启（authenticate=0）");

	/* 4-6. Both copies: writable, no bad blocks, fully readable. */
	char sums[2][65] = { "", "" };
	int copies = ap[1] ? 2 : 1;
	for (int j = 0; j < copies; j++) {
		const struct ipqi_part_info *p = find_off(parts, n, ap[j]->offset);
		struct bb_flash f;
		uint8_t *data, sum[32];
		int r;

		S.idx_appsbl[j] = p->idx;
		if (!p->writable) {
			fail(C_WRITABLE, "原厂内核把 %s 设成了只读，不能从系统里安装，请用 TTL", p->name);
			return;
		}
		if ((r = ipqi_open(p->idx, 0, &f))) {
			fail(C_WRITABLE, "打不开 %s（%s）", p->name, strerror(-r));
			return;
		}
		for (uint32_t b = 0; b < f.size; b += f.erase_size) {
			if ((r = f.is_bad(f.ctx, b))) {
				f.close(f.ctx);
				fail(C_BAD, "%s 在 0x%x 处有坏块，拒绝写入", p->name, b);
				return;
			}
		}
		data = malloc(f.size);
		r = data ? bb_flash_read(&f, 0, data, f.size) : -ENOMEM;
		f.close(f.ctx);
		if (r) {
			free(data);
			fail(C_READ, "%s 读不出来（%s），可能有 ECC 错误", p->name, strerror(-r));
			return;
		}
		ipqi_sha256(data, p->size, sum);
		hex(sum, 32, sums[j]);
		free(data);
	}
	pass(C_WRITABLE, "可写");
	pass(C_BAD, "没有");
	pass(C_READ, copies == 2 ? "两份都读出来了，SHA-256 %.16s… / %.16s…%s" : "读出来了，SHA-256 %.16s…%s",
	     sums[0], copies == 2 ? sums[1] : "",
	     copies == 2 && strcmp(sums[0], sums[1]) ? "（两份不一样）" : "");

	/* 7. Which copy boots. Both BOOTCONFIG records must agree. */
	if (S.prof->slots == IPQI_SLOTS_SINGLE) {
		S.active = 0;
		pass(C_SLOT, "单 U-Boot 机型，不涉及");
	} else {
		const char *names[2] = { "0:BOOTCONFIG", "0:BOOTCONFIG1" };
		uint32_t sel[2];

		for (int j = 0; j < 2; j++) {
			const struct ipqi_part_info *p = find_name(parts, n, names[j]);
			uint8_t rec[BB_BC_RECORD_BYTES];
			struct bb_flash f;
			struct bb_bc bc;
			enum bb_bc_status st;

			if (!p || ipqi_open(p->idx, 0, &f)) {
				fail(C_SLOT, "打不开 %s", names[j]);
				return;
			}
			int r = bb_flash_read(&f, 0, rec, sizeof(rec));
			f.close(f.ctx);
			if (r || (st = bb_bc_parse(rec, sizeof(rec), &bc)) != BB_BC_OK || !bc.have_appsbl ||
			    bc.appsbl_selector > 1) {
				fail(C_SLOT, "%s 无法解析，不确定哪份 U-Boot 在用", names[j]);
				return;
			}
			sel[j] = bc.appsbl_selector;
		}
		if (sel[0] != sel[1]) {
			fail(C_SLOT, "两份 BOOTCONFIG 说法不一（%u / %u），不确定哪份 U-Boot 在用",
			     sel[0], sel[1]);
			return;
		}
		S.active = sel[0];
		pass(C_SLOT, "正在用%s的那份 U-Boot，会先写另一份", S.active ? "偏移较高" : "偏移较低");
	}

	/* 8. Our U-Boot for this model, from the package. */
	if (!S.payload) {
		char err[128];

		S.payload = ipqi_payload(S.prof->payload, &S.payload_len, err, sizeof(err));
		if (!S.payload) {
			fail(C_PAYLOAD, "%s", err);
			return;
		}
	}
	if (S.payload_len > ap[0]->size) {
		fail(C_PAYLOAD, "U-Boot 比分区还大");
		return;
	}
	uint8_t sum[32];
	char sh[65];
	ipqi_sha256(S.payload, S.payload_len, sum);
	hex(sum, 32, sh);
	pass(C_PAYLOAD, "%s，%zu 字节，SHA-256 %.16s…", ipqi_pkg_version(), S.payload_len, sh);
}

/* ---- backup ---- */

static void backup_path(char *buf, size_t len)
{
	snprintf(buf, len, "%s/backup.zip", S.dir);
}

static void do_backup(void)
{
	struct ipqi_part_info parts[IPQI_MAX_PARTS];
	struct bb_flash fl[BB_BACKUP_MAX];
	struct bb_backup_entry e[BB_BACKUP_MAX];
	char path[512];
	unsigned m = 0;
	int n = ipqi_parts(parts, IPQI_MAX_PARTS), ret;
	FILE *out;

	S.backup_ready = S.backup_downloaded = 0;
	if (!S.prof || !S.c[C_LAYOUT].ok) {
		set_result("backup", "not_ready", "机型或分区表检查没有通过，不能备份");
		return;
	}
	for (const char *const *b = S.prof->backup; *b && m < BB_BACKUP_MAX; b++) {
		const struct ipqi_part_info *p = NULL;

		/* By the profile's physical offset: names of failsafe pairs may be swapped. */
		for (unsigned i = 0; i < S.prof->layout_len; i++)
			if (!strcmp(S.prof->layout[i].name, *b))
				p = find_off(parts, n, S.prof->layout[i].offset);
		if (!p || ipqi_open(p->idx, 0, &fl[m])) {
			set_result("backup", "missing", "打不开分区 %s，无法备份", *b);
			goto close;
		}
		e[m].part = &fl[m];
		e[m].role = "startup";
		snprintf(e[m].file, sizeof(e[m].file), "%06x_%s.bin", p->offset, *b);
		for (char *c = e[m].file; *c; c++)
			if (*c == ':')
				*c = '_';
		m++;
	}
	backup_path(path, sizeof(path));
	out = fopen(path, "wb");
	if (!out) {
		set_result("backup", "io", "无法创建备份文件");
		goto close;
	}
	ret = bb_backup_write(out, e, m, &S.backup);
	if (fclose(out) || ret) {
		unlink(path);
		set_result("backup", "io", "备份失败（读取出错或内存不足）");
		goto close;
	}
	out = fopen(path, "rb");
	ret = out ? bb_backup_verify(out, &S.backup) : -EIO;
	if (out)
		fclose(out);
	if (ret) {
		unlink(path);
		set_result("backup", "verify", "备份读回校验失败，请重试");
		goto close;
	}
	S.backup_ready = 1;
	set_result("backup", "ok", S.backup.unreadable_blocks ?
		   "备份已生成，但有读不出的块已用 0xFF 代替，详见其中的 manifest.json" :
		   "备份已生成，请下载保存");
close:
	for (unsigned i = 0; i < m; i++)
		fl[i].close(fl[i].ctx);
}

/* ---- install ---- */

static int write_copy(int j, const uint8_t *img, int *skipped)
{
	struct bb_flash f;
	uint8_t *cur;
	int r;

	*skipped = 0;
	if ((r = ipqi_open(S.idx_appsbl[j], 1, &f)))
		return r;
	cur = malloc(f.size);
	r = cur ? bb_flash_read(&f, 0, cur, f.size) : -ENOMEM;
	if (!r && !memcmp(cur, img, f.size)) {
		*skipped = 1;
	} else if (cur) {
		r = 0;
		for (uint32_t b = 0; !r && b < f.size; b += f.erase_size)
			r = bb_flash_rewrite_boot_block(&f, b, img + b);
		/* Whole-partition read-back after the per-block checks. */
		if (!r)
			r = bb_flash_read(&f, 0, cur, f.size);
		if (!r && memcmp(cur, img, f.size))
			r = -EIO;
	}
	free(cur);
	f.close(f.ctx);
	return r;
}

static void do_install(void)
{
	struct ipqi_part_info parts[IPQI_MAX_PARTS];
	int n, first, second, sk1, sk2, r;
	uint8_t *img;

	if (!ready()) {
		set_result("install", "not_ready", "还有检查没通过，不能写入");
		return;
	}
	if (!S.backup_downloaded) {
		set_result("install", "no_backup", "请先下载备份");
		return;
	}
	n = ipqi_parts(parts, IPQI_MAX_PARTS);
	img = NULL;
	for (int i = 0; i < n; i++)
		if (parts[i].idx == S.idx_appsbl[0])
			img = image_for(parts[i].size);
	if (!img) {
		set_result("install", "no_mem", "内存不足");
		return;
	}
	if (S.idx_appsbl[1] < 0) {
		r = write_copy(0, img, &sk1);
		free(img);
		if (r)
			set_result("install", "write", "U-Boot 写入失败（%s）。不要重启，先重试；还不行就用备份和 TTL 恢复",
				   strerror(-r));
		else
			set_result("install", "ok", sk1 ? "已经是这个版本，没有写入" : "写入并读回核对完成，可以重启");
		S.installed = !r;
		return;
	}
	first = !S.active;
	second = S.active;
	r = write_copy(first, img, &sk1);
	if (r) {
		free(img);
		set_result("install", "write_first",
			   "备用的那份 U-Boot 写入失败（%s）。正在用的那份没动，重启没有问题，可以重试",
			   strerror(-r));
		return;
	}
	r = write_copy(second, img, &sk2);
	free(img);
	if (r) {
		set_result("install", "write_second",
			   "正在用的那份 U-Boot 写入失败（%s）。另一份已是新 U-Boot。先不要重启，点重试",
			   strerror(-r));
		return;
	}
	S.installed = 1;
	set_result("install", "ok", sk1 && sk2 ? "两份都已经是这个版本，没有写入" :
		   "两份 U-Boot 都已写入并读回核对。重启后就是新 U-Boot，原厂系统照常启动");
}

/* ---- HTTP ---- */

struct buf {
	char *p;
	size_t len, cap;
};

static void bprintf(struct buf *b, const char *fmt, ...)
{
	va_list ap;
	int n;

	for (;;) {
		va_start(ap, fmt);
		n = vsnprintf(b->p + b->len, b->cap - b->len, fmt, ap);
		va_end(ap);
		if (n < 0)
			return;
		if ((size_t)n < b->cap - b->len) {
			b->len += n;
			return;
		}
		b->cap = b->cap * 2 + n;
		b->p = realloc(b->p, b->cap);
		if (!b->p)
			exit(1);
	}
}

static void bstr(struct buf *b, const char *s)
{
	bprintf(b, "\"");
	for (; s && *s; s++) {
		unsigned char c = *s;

		if (c == '"' || c == '\\')
			bprintf(b, "\\%c", c);
		else if (c < 0x20)
			bprintf(b, "\\u%04x", c);
		else
			bprintf(b, "%c", c);
	}
	bprintf(b, "\"");
}

static int send_all(int fd, const void *p, size_t n)
{
	const char *c = p;

	while (n) {
		ssize_t w = write(fd, c, n);

		if (w < 0 && errno == EINTR)
			continue;
		if (w <= 0)
			return -1;
		c += w;
		n -= w;
	}
	return 0;
}

static void respond(int fd, int status, const char *type, const void *body, size_t len)
{
	char head[384];
	int n = snprintf(head, sizeof(head),
			 "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %zu\r\n"
			 "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
			 "Connection: close\r\n\r\n",
			 status, status == 200 ? "OK" : "Error", type, len);

	send_all(fd, head, n);
	send_all(fd, body, len);
}

static void state_json(struct buf *b)
{
	bprintf(b, "{\"version\":");
	bstr(b, ipqi_pkg_version());
	bprintf(b, ",\"sim\":%s,\"model\":", ipqi_sim() ? "true" : "false");
	if (S.prof) {
		bprintf(b, "{\"id\":");
		bstr(b, S.prof->id);
		bprintf(b, ",\"title\":");
		bstr(b, S.prof->title);
		bprintf(b, "}");
	} else {
		bprintf(b, "null");
	}
	bprintf(b, ",\"checks\":[");
	for (int k = 0; k < C_COUNT; k++) {
		bprintf(b, "%s{\"label\":", k ? "," : "");
		bstr(b, check_label[k]);
		bprintf(b, ",\"ok\":%s,\"detail\":", S.c[k].ok ? "true" : "false");
		bstr(b, S.c[k].detail);
		bprintf(b, "}");
	}
	bprintf(b, "],\"ready\":%s,\"backup\":{\"ready\":%s,\"downloaded\":%s,\"bytes\":%llu,\"sha256\":",
		ready() ? "true" : "false", S.backup_ready ? "true" : "false",
		S.backup_downloaded ? "true" : "false", (unsigned long long)S.backup.bytes);
	bstr(b, S.backup_ready ? S.backup.sha256 : "");
	bprintf(b, "},\"installed\":%s,\"result\":{\"action\":", S.installed ? "true" : "false");
	bstr(b, S.action);
	bprintf(b, ",\"code\":");
	bstr(b, S.code);
	bprintf(b, ",\"message\":");
	bstr(b, S.message);
	bprintf(b, "}}\n");
}

static void serve_backup(int fd)
{
	char head[256], chunk[65536], path[512];
	FILE *f;
	size_t n;
	uint64_t sent = 0;
	int ok;

	backup_path(path, sizeof(path));
	f = S.backup_ready ? fopen(path, "rb") : NULL;
	if (!f) {
		respond(fd, 404, "text/plain", "no backup\n", 10);
		return;
	}
	n = snprintf(head, sizeof(head),
		     "HTTP/1.1 200 OK\r\nContent-Type: application/zip\r\nContent-Length: %llu\r\n"
		     "Content-Disposition: attachment; filename=\"%s-backup.zip\"\r\n"
		     "Cache-Control: no-store\r\nConnection: close\r\n\r\n",
		     (unsigned long long)S.backup.bytes, S.prof ? S.prof->id : "ipqi");
	ok = !send_all(fd, head, n);
	while (ok && (n = fread(chunk, 1, sizeof(chunk), f)) > 0) {
		ok = !send_all(fd, chunk, n);
		if (ok)
			sent += n;
	}
	if (ok && !ferror(f) && sent == S.backup.bytes)
		S.backup_downloaded = 1;
	fclose(f);
}

static int handle(int fd)
{
	char req[8192], method[8], path[128];
	size_t got = 0;
	struct buf b = { malloc(8192), 0, 8192 };
	int post, quit = 0;

	while (got < sizeof(req) - 1) {
		ssize_t r = read(fd, req + got, sizeof(req) - 1 - got);

		if (r <= 0)
			break;
		got += r;
		req[got] = 0;
		if (strstr(req, "\r\n\r\n"))
			break;
	}
	req[got] = 0;
	if (!b.p || sscanf(req, "%7s %127s", method, path) != 2) {
		free(b.p);
		return 0;
	}
	post = !strcmp(method, "POST");
	/* A custom header: other web pages cannot send it without a CORS preflight. */
	if (post && !strcasestr(req, "\r\nX-IPQI: 1\r\n")) {
		respond(fd, 403, "text/plain", "forbidden\n", 10);
	} else if (!post && (!strcmp(path, "/") || !strcmp(path, "/index.html"))) {
		respond(fd, 200, "text/html; charset=utf-8", www_index_html, www_index_html_len);
	} else if (!post && !strcmp(path, "/backup.zip")) {
		serve_backup(fd);
	} else if (!post && !strcmp(path, "/api/state")) {
		state_json(&b);
		respond(fd, 200, "application/json; charset=utf-8", b.p, b.len);
	} else if (post && !strncmp(path, "/api/", 5)) {
		const char *api = path + 5;

		if (!strcmp(api, "backup"))
			do_backup();
		else if (!strcmp(api, "install"))
			do_install();
		else if (!strcmp(api, "recheck"))
			run_checks();
		else if (!strcmp(api, "reboot"))
			set_result("reboot", "ok", ipqi_sim() ? "（模拟）正在重启" : "正在重启");
		else if (!strcmp(api, "quit"))
			set_result("quit", "ok", "安装程序已退出，原厂系统没有被改动之外的任何东西");
		else
			api = NULL;
		if (!api) {
			respond(fd, 404, "text/plain", "not found\n", 10);
		} else {
			state_json(&b);
			respond(fd, 200, "application/json; charset=utf-8", b.p, b.len);
			quit = !strcmp(api, "quit") ? 1 : !strcmp(api, "reboot") ? 2 : 0;
		}
	} else {
		respond(fd, 404, "text/plain", "not found\n", 10);
	}
	free(b.p);
	return quit;
}

static int serve(int port)
{
	struct sockaddr_in a = { .sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_ANY) };
	int s, one = 1;

	signal(SIGPIPE, SIG_IGN);
	signal(SIGHUP, SIG_IGN);
	run_checks();
	a.sin_port = htons(port);
	s = socket(AF_INET, SOCK_STREAM, 0);
	/* The upload page's uhttpd may still be releasing the port. */
	for (int tries = 0; s >= 0; tries++) {
		setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
		if (!bind(s, (struct sockaddr *)&a, sizeof(a)) && !listen(s, 8))
			break;
		if (tries == 20) {
			perror("ipqi: listen");
			return 1;
		}
		sleep(1);
	}
	fprintf(stderr, "ipqi %s: listening on %d\n", ipqi_pkg_version(), port);
	for (;;) {
		int c = accept(s, NULL, NULL), q;
		struct timeval tv = { 10, 0 };

		if (c < 0)
			continue;
		setsockopt(c, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
		q = handle(c);
		close(c);
		if (q == 1)
			return 0;
		if (q == 2) {
			sync();
			sleep(1);
			if (!ipqi_sim())
				reboot(RB_AUTOBOOT);
			return 0;
		}
	}
}

int main(int argc, char **argv)
{
	int port = 8088, opt;

	if (argc < 2) {
		fprintf(stderr, "usage: %s serve [-p port] [-d dir] | check\n", argv[0]);
		return 2;
	}
	optind = 2;
	while ((opt = getopt(argc, argv, "p:d:")) != -1) {
		if (opt == 'p')
			port = atoi(optarg);
		else if (opt == 'd')
			S.dir = optarg;
		else
			return 2;
	}
	if (!strcmp(argv[1], "check")) {
		struct buf b = { malloc(8192), 0, 8192 };

		run_checks();
		state_json(&b);
		fwrite(b.p, 1, b.len, stdout);
		return ready() ? 0 : 1;
	}
	if (!strcmp(argv[1], "serve")) {
		mkdir(S.dir, 0700);
		return serve(port);
	}
	return 2;
}
