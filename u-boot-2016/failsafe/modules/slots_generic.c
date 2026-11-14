// SPDX-License-Identifier: GPL-2.0
/*
 * Rescue page system slots on boards without the H3C layout code: which
 * systems are there (slot_probe) and which one boots by default (slot_ops).
 * Same JSON as the H3C module, so the page needs no board knowledge. Booting
 * a slot once is not offered: on BOOTCONFIG boards SBL names the partitions
 * after the slot it booted, so "set as default, then reboot" is the one
 * switch that every backend does the same way.
 */
#include <common.h>
#include <net/httpd.h>
#include <ipq_api.h>
#include <slot_ops.h>
#include <slot_probe.h>
#include <asm/arch-qca-common/smem.h>
#include "modules.h"

#define SLOT_N 2

struct gslot {
	unsigned int slot;		/* backend slot number (0/1) */
	char part[16];
	u32 offset, size;
	struct slot_probe probe;
	int probed, ret;
};
static struct gslot gslots[SLOT_N];
static unsigned int gslot_n;
static int gslots_ready;
/* Set after a write that may have left the two BOOTCONFIG copies different;
 * cleared only by a reboot, so the page cannot write again on top of it. */
static int gdefault_locked;
static char gjson[3072];

static void answer(struct httpd_response *r, int code, const char *json)
{
	r->status = HTTP_RESP_STD;
	r->info.code = code;
	r->info.connection_close = 1;
	r->info.content_type = "application/json";
	r->data = json;
	r->size = strlen(json);
}

static void scan(void)
{
	unsigned int i, n = slot_count();

	memset(gslots, 0, sizeof(gslots));
	gslot_n = 0;
	for (i = 0; i < n && i < SLOT_N; i++) {
		struct gslot *g = &gslots[gslot_n];

		g->slot = i;
		strlcpy(g->part, slot_part_name(i), sizeof(g->part));
		if (getpart_offset_size(g->part, &g->offset, &g->size) || !g->size)
			continue;
		g->ret = slot_probe_read(g->part, g->offset, g->size, &g->probe);
		g->probed = 1;
		gslot_n++;
	}
	gslots_ready = 1;
}

static void format(void)
{
	char sys[200], ker[72], err[100];
	unsigned int i, phys;
	int len, n;

	len = snprintf(gjson, sizeof(gjson),
		       "{\"read_only\":false,\"boot_supported\":false,\"default_supported\":true,\"mode\":\"%s\",\"count\":%u,\"slots\":[",
		       gslot_n == 2 ? "dual" : "single", gslot_n);
	for (i = 0; i < gslot_n && len > 0 && (size_t)len < sizeof(gjson); i++) {
		const struct gslot *g = &gslots[i];
		const char *s = g->probe.system;

		phys = 1;
		if (gslot_n == 2 && g->offset > gslots[1 - i].offset)
			phys = 2;
		json_escape(s, sys, sizeof(sys));
		json_escape(g->probe.kernel, ker, sizeof(ker));
		json_escape(g->probe.error, err, sizeof(err));
		n = snprintf(gjson + len, sizeof(gjson) - len,
			     "%s{\"name\":\"%s\",\"part_name\":\"%s\",\"slot\":%u,\"display_index\":%u,\"physical_index\":%u,"
			     "\"offset\":\"0x%x\",\"physical_end\":\"0x%x\",\"size\":\"0x%x\",\"boot_command\":\"\","
			     "\"label\":\"%s\",\"known\":%s,\"detection\":\"%s\",\"type\":\"%s\",\"version\":\"%s\","
			     "\"kernel\":\"%s\",\"firmware_version\":null,\"error\":\"%s\"}",
			     i ? "," : "", g->part, g->part, g->slot, i, phys,
			     g->offset, g->offset + g->size - 1, g->size,
			     s[0] ? sys : "Unknown system", s[0] ? "true" : "false",
			     g->ret ? "unreadable" : g->probe.error[0] ? "rootfs_unreadable" :
			     s[0] ? "rootfs_release_file" : "no_release_file",
			     !s[0] ? "unknown" : !strncmp(s, "OpenWrt ", 8) ? "OpenWrt" :
			     !strncmp(s, "ImmortalWrt ", 12) ? "ImmortalWrt" : "Other",
			     s[0] ? sys : "unknown", ker, err);
		if (n < 0 || (size_t)n >= sizeof(gjson) - len)
			goto too_large;
		len += n;
	}
	n = snprintf(gjson + len, sizeof(gjson) - len, "]}");
	if (n >= 0 && (size_t)n < sizeof(gjson) - len)
		return;
too_large:
	strlcpy(gjson, "{\"mode\":\"unsupported\",\"count\":0,\"slots\":[],\"error\":\"response_too_large\"}",
		sizeof(gjson));
}

static void slots_handler(enum httpd_uri_handler_status status,
			  struct httpd_request *request,
			  struct httpd_response *response)
{
	if (status != HTTP_CB_NEW)
		return;
	if (!request || request->method != HTTP_GET) {
		answer(response, 405, "{\"error\":\"GET required\"}");
		return;
	}
	if (!gslots_ready) {
		scan();
		format();
	}
	answer(response, 200, gjson);
}

/* Which partition name boots by default; null when it cannot be read. */
static const char *default_name(void)
{
	int d;

	if (slot_count() < 2)
		return "rootfs";
	d = slot_default_rootfs();
	if (d != 0 && d != 1)
		return NULL;
	return slot_part_name((unsigned int)d);
}

static void default_handler(enum httpd_uri_handler_status status,
			    struct httpd_request *request,
			    struct httpd_response *response)
{
	static char reply[200];
	struct httpd_form_value *v = NULL;
	const char *cur;
	unsigned int i, want = SLOT_N, found = 0;
	int ret, ready = 0;

	if (status != HTTP_CB_NEW)
		return;
	if (!request || (request->method != HTTP_GET && request->method != HTTP_POST)) {
		answer(response, 405, "{\"status\":\"fail\",\"error\":\"method_not_allowed\"}");
		return;
	}
	if (request->method == HTTP_GET) {
		cur = default_name();
		snprintf(reply, sizeof(reply),
			 "{\"default\":%s%s%s,\"can_change\":%s,\"locked\":%s,"
			 "\"default_applies_to\":\"next_boot\",\"auto_web\":false}",
			 cur ? "\"" : "", cur ? cur : "null", cur ? "\"" : "",
			 slot_count() == 2 && cur && !gdefault_locked ? "true" : "false",
			 gdefault_locked ? "true" : "false");
		answer(response, 200, reply);
		return;
	}
	for (i = 0; i < request->form.count; i++)
		if (request->form.values[i].name &&
		    !strcmp(request->form.values[i].name, "target")) {
			v = &request->form.values[i];
			found++;
		}
	if (request->form.count != 1 || found != 1 || !v || !v->data ||
	    memchr(v->data, 0, v->size)) {
		answer(response, 400, "{\"status\":\"fail\",\"error\":\"invalid_target\"}");
		return;
	}
	for (i = 0; i < slot_count() && i < SLOT_N; i++)
		if (strlen(slot_part_name(i)) == v->size &&
		    !memcmp(slot_part_name(i), v->data, v->size))
			want = i;
	if (slot_count() < 2 || want >= SLOT_N) {
		answer(response, 400, "{\"status\":\"fail\",\"error\":\"invalid_target\"}");
		return;
	}
	if (gdefault_locked) {
		answer(response, 409, "{\"status\":\"fail\",\"error\":\"locked_after_partial_write\"}");
		return;
	}
	/* Refuse a slot that holds no UBI system before touching BOOTCONFIG. */
	if (!gslots_ready) {
		scan();
		format();
	}
	for (i = 0; i < gslot_n; i++)
		if (gslots[i].slot == want && gslots[i].probed && !gslots[i].ret)
			ready = 1;
	if (!ready) {
		answer(response, 409, "{\"status\":\"fail\",\"error\":\"target_slot_has_no_system\"}");
		return;
	}
	/* From here a failure may have written one copy: lock until reboot. */
	ret = slot_set_default(want);
	cur = ret ? NULL : default_name();
	if (ret || !cur || strcmp(cur, slot_part_name(want))) {
		gdefault_locked = 1;
		snprintf(reply, sizeof(reply),
			 "{\"status\":\"partial\",\"error\":\"%s\",\"errno\":%d}",
			 ret ? "default_not_saved" : "default_not_confirmed", ret);
		answer(response, 409, reply);
		return;
	}
	snprintf(reply, sizeof(reply), "{\"status\":\"ok\",\"default\":\"%s\"}", cur);
	answer(response, 200, reply);
}

/* A firmware write changed a slot: identify it again on the next GET. */
void slots_generic_invalidate_cache(void)
{
	gslots_ready = 0;
}

void slots_generic_register_uri_handlers(struct httpd_instance *inst)
{
	httpd_register_uri_handler(inst, "/boot/slots", slots_handler, NULL);
	httpd_register_uri_handler(inst, "/boot/default", default_handler, NULL);
}
