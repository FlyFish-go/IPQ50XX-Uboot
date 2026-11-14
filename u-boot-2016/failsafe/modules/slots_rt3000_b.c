// SPDX-License-Identifier: GPL-2.0
/* H3C slot summary: layout from the H3C table, identity from slot_probe. */
#include <common.h>
#include <exports.h>
#include <asm/errno.h>
#include <linux/mtd/partitions.h>
#include <nand.h>
#include <net/httpd.h>
#include <asm/arch-qca-common/smem.h>
#include <rt3000_b_layout.h>
#include <slot_probe.h>
#include "modules.h"

DECLARE_GLOBAL_DATA_PTR;

#define SLOT_N 2

struct slot_info {
 u64 offset, size;
 unsigned int display_index;
 char label[96], part_name[64];
 char status[16], type[16], version[97], kernel[33], detection[40], error[48];
};
static struct slot_info slots[SLOT_N];
static char slots_json[4096];
static char escaped_part[SLOT_N][128];
static char escaped_label[SLOT_N][128];
static char escaped_version[SLOT_N][256];
static char escaped_kernel[SLOT_N][72];
#define SLOT_ACCESS_JSON "\"read_only\":false,\"boot_supported\":true,"
static int slots_ready;
static struct rt3_layout scanned_layout;
static int environment_restored = 1;

static void set_unknown(struct slot_info *s)
{
 strlcpy(s->status, "unknown", sizeof(s->status));
 strlcpy(s->type, "unknown", sizeof(s->type));
 strlcpy(s->version, "unknown", sizeof(s->version));
 strlcpy(s->label, "Unknown system", sizeof(s->label));
 strlcpy(s->detection, "no_release_file", sizeof(s->detection));
}
static void set_error(struct slot_info *s, const char *e)
{
 set_unknown(s);
 strlcpy(s->detection, "unreadable", sizeof(s->detection));
 strlcpy(s->error, e, sizeof(s->error));
}
/* Identity = what the slot itself says (release file, kernel name); no table. */
static void read_slot(struct slot_info *s)
{
 struct slot_probe p;
 int ret = slot_probe_read(s->part_name, s->offset, s->size, &p);

 if (p.env_lost)
  environment_restored = 0;
 set_unknown(s);
 strlcpy(s->kernel, p.kernel, sizeof(s->kernel));
 if (ret) {
  set_error(s, p.error[0] ? p.error : "ubi_read_failed");
  return;
 }
 if (p.error[0]) {
  strlcpy(s->detection, "rootfs_unreadable", sizeof(s->detection));
  strlcpy(s->error, p.error, sizeof(s->error));
  return;
 }
 if (!p.system[0])
  return;
 strlcpy(s->status, "known", sizeof(s->status));
 if (!strncmp(p.system, "OpenWrt ", 8))
  strlcpy(s->type, "OpenWrt", sizeof(s->type));
 else if (!strncmp(p.system, "ImmortalWrt ", 12))
  strlcpy(s->type, "ImmortalWrt", sizeof(s->type));
 else if (!strncmp(p.system, "LEDE ", 5))
  strlcpy(s->type, "LEDE", sizeof(s->type));
 else
  strlcpy(s->type, "Other", sizeof(s->type));
 strlcpy(s->version, p.system, sizeof(s->version));
 strlcpy(s->label, p.system, sizeof(s->label));
 strlcpy(s->detection, "rootfs_release_file", sizeof(s->detection));
}
static void format_slots(const struct rt3_layout *layout)
{
 int len,i,n,cmdlen; unsigned int physical_index; u64 physical_end;
 char boot_command[48];
 const char *mode=rt3_layout_mode_name(layout->mode);
 len=snprintf(slots_json,sizeof(slots_json),
  "{\"environment_restored\":%s,\"mode\":\"%s\",\"count\":%u,\"fingerprint\":\"0x%08x\",%s\"slots\":[",
  environment_restored?"true":"false",mode,layout->count,layout->fingerprint,SLOT_ACCESS_JSON);
 if(len<0||(size_t)len>=sizeof(slots_json))goto too_large;
 for(i=0;i<layout->count;i++){
  physical_index=1;
  if(layout->count==2&&slots[i].offset>slots[1-i].offset)physical_index=2;
  physical_end=slots[i].offset+slots[i].size-1;
  json_escape(slots[i].part_name,escaped_part[i],sizeof(escaped_part[i]));
  json_escape(slots[i].label,escaped_label[i],sizeof(escaped_label[i]));
  json_escape(slots[i].version,escaped_version[i],sizeof(escaped_version[i]));
  json_escape(slots[i].kernel,escaped_kernel[i],sizeof(escaped_kernel[i]));
  cmdlen=snprintf(boot_command,sizeof(boot_command),"bootipq %s",slots[i].part_name);
  if(cmdlen<0||(size_t)cmdlen>=sizeof(boot_command))goto too_large;
  n=snprintf(slots_json+len,sizeof(slots_json)-len,
   "%s{\"name\":\"%s\",\"part_name\":\"%s\",\"display_index\":%u,\"physical_index\":%u,\"offset\":\"0x%llx\",\"physical_end\":\"0x%llx\",\"size\":\"0x%llx\",\"boot_command\":\"%s\",\"label\":\"%s\",\"known\":%s,\"detection\":\"%s\",\"type\":\"%s\",\"version\":\"%s\",\"kernel\":\"%s\",\"firmware_version\":null,\"error\":\"%s\"}",
   i?",":"",escaped_part[i],escaped_part[i],slots[i].display_index,physical_index,
   (unsigned long long)slots[i].offset,(unsigned long long)physical_end,(unsigned long long)slots[i].size,
   boot_command,escaped_label[i],!strcmp(slots[i].status,"known")?"true":"false",
   slots[i].detection,slots[i].type,escaped_version[i],escaped_kernel[i],
   slots[i].error);
  if(n<0||(size_t)n>=sizeof(slots_json)-len)goto too_large;
  len+=n;
 }
 n=snprintf(slots_json+len,sizeof(slots_json)-len,"]}");
 if(n<0||(size_t)n>=sizeof(slots_json)-len)goto too_large;
 return;
too_large:
 strlcpy(slots_json,"{\"environment_restored\":false,\"mode\":\"unsupported\",\"count\":0,\"slots\":[],\"error\":\"response_too_large\"}",sizeof(slots_json));
}

static int same_layout(const struct rt3_layout *a, const struct rt3_layout *b)
{
        unsigned int i;
        if (a->fingerprint != b->fingerprint || a->mode != b->mode ||
            a->count != b->count || a->count > RT3_LAYOUT_MAX_PARTITIONS)
                return 0;
        for (i = 0; i < a->count; i++) {
                if (a->parts[i].display_index != b->parts[i].display_index ||
                    a->parts[i].offset != b->parts[i].offset ||
                    a->parts[i].size != b->parts[i].size ||
                    strcmp(a->parts[i].name, b->parts[i].name))
                        return 0;
        }
        return 1;
}

static void scan_slots(const struct rt3_layout *layout)
{
        const struct rt3_partition *part;
        int i;
        memset(slots, 0, sizeof(slots));
        environment_restored = 1;
        for (i = 0; i < layout->count; i++) {
                struct slot_info *slot = &slots[i];
                part = &layout->parts[i];
                slot->offset = part->offset;
                slot->size = part->size;
                slot->display_index = part->display_index;
                strlcpy(slot->part_name, part->name, sizeof(slot->part_name));
                if (!environment_restored) {
                        set_error(slot, "environment_restore_failed");
                        continue;
                }
                read_slot(slot);
        }
        format_slots(layout);
        slots_ready = 1;
}

void slots_rt3000_b_invalidate_cache(void)
{
	slots_ready = 0;
	memset(slots, 0, sizeof(slots));
	memset(slots_json, 0, sizeof(slots_json));
	rt3_layout_invalidate_cache();
}

static void boot_slots_handler(enum httpd_uri_handler_status status,
 struct httpd_request *request, struct httpd_response *response)
{
 struct rt3_layout layout;
 int ret;

 if (status != HTTP_CB_NEW) return;
 response->status = HTTP_RESP_STD;
 response->info.code = 200;
 response->info.connection_close = 1;
 response->info.content_type = "application/json";
 if (!request || request->method != HTTP_GET) {
  response->info.code = 405;
  response->data = "{\"error\":\"GET required\"}";
  response->size = strlen(response->data);
  return;
 }
 memset(&layout, 0, sizeof(layout));
 layout.mode = RT3_LAYOUT_UNSUPPORTED;
 ret = rt3_layout_read(&layout);
 if (ret || layout.mode == RT3_LAYOUT_UNSUPPORTED ||
     !layout.count || layout.count > SLOT_N) {
  memset(slots, 0, sizeof(slots));
  set_error(&slots[0], ret ? "layout_validation_failed" :
            "unsupported_rootfs_layout");
  layout.mode = RT3_LAYOUT_UNSUPPORTED;
  layout.count = 0;
  layout.fingerprint = 0;
  format_slots(&layout);
  slots_ready = 0;
 } else if (!slots_ready || !same_layout(&scanned_layout, &layout)) {
  scan_slots(&layout);
  scanned_layout = layout;
 }
 response->data = slots_json;
 response->size = strlen(response->data);
}
void slots_rt3000_b_register_uri_handlers(struct httpd_instance *inst)
{
 httpd_register_uri_handler(inst, "/boot/slots", boot_slots_handler, NULL);
}

