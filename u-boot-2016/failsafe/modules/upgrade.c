/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Copyright (C) 2022 MediaTek Inc. All Rights Reserved.
 *
 * Author: Weijie Gao <weijie.gao@mediatek.com>
 *
 * Failsafe upgrade module
 */

/*
 * Modified by: chenxin527
 */

#include <common.h>
#include <asm/errno.h>
#include <malloc.h>
#include <net/tcp.h>
#include <net/httpd.h>
#include <failsafe/failsafe.h>
#include <ipq_api.h>
#ifndef CONFIG_H3C_IPQ5018_COMMON
#include <u-boot/md5.h>
#endif
#ifdef CONFIG_H3C_IPQ5018_COMMON
#include <rt3000_b_metadata.h>
#endif

#include "modules.h"

struct upload_session {
	char header_buf[4096];
	int ret;
    int body_sent;
};

struct result_session {
	char buf[4096];
	int ret;
	int body_sent;
	bool auto_reboot;
	u32 gen;
#ifndef CONFIG_H3C_IPQ5018_COMMON
	u32 armed_id;	/* upload this /result was sent for */
#endif
};

static const struct {
	upgrade_type_t type;
	const char *label;
} upgrade_types[] = {
	{ WEBFAILSAFE_UPGRADE_TYPE_FIRMWARE, "firmware" },
	{ WEBFAILSAFE_UPGRADE_TYPE_UBOOT, "uboot" },
	{ WEBFAILSAFE_UPGRADE_TYPE_ART, "art" },
	{ WEBFAILSAFE_UPGRADE_TYPE_CDT, "cdt" },
	{ WEBFAILSAFE_UPGRADE_TYPE_PTABLE, "ptable" },
	{ WEBFAILSAFE_UPGRADE_TYPE_SIMG, "simg" },
	{ WEBFAILSAFE_UPGRADE_TYPE_INITRAMFS, "initramfs" },
	{ WEBFAILSAFE_UPGRADE_TYPE_OEMDATA, "oemdata" }
};

bool auto_action_pending;
const void *upload_data;
upgrade_type_t upgrade_type;

static u32 fs_upload_id;
static u32 upload_data_id;
static size_t upload_size;
#ifndef CONFIG_H3C_IPQ5018_COMMON
/* Shared-RAM generation and MD5 of the last upload that passed validation:
 * a write or a RAM boot uses the bytes only while both still match. */
static u32 upload_data_gen;
static u8 upload_data_md5[16];
static bool upload_data_md5_valid;

bool failsafe_upload_unchanged(void)
{
	u8 now[16];

	if (!upload_data_md5_valid || upload_data_gen != httpd_upload_buffer_gen())
		return false;
	md5((u8 *)upload_data, upload_size, now);
	return !memcmp(now, upload_data_md5, sizeof(now));
}
#endif

#ifdef CONFIG_H3C_IPQ5018_COMMON
static int metadata_kind_for_upgrade(upgrade_type_t type, enum rt3_md_kind *kind)
{
	if (!kind) return -EINVAL;
	switch (type) {
	case WEBFAILSAFE_UPGRADE_TYPE_UBOOT: *kind=RT3_MD_UBOOT; return 1;
	case WEBFAILSAFE_UPGRADE_TYPE_ART: *kind=RT3_MD_ART; return 1;
	case WEBFAILSAFE_UPGRADE_TYPE_CDT: *kind=RT3_MD_CDT; return 1;
	case WEBFAILSAFE_UPGRADE_TYPE_PTABLE: *kind=RT3_MD_MIBIB; return 1;
	default: return 0;
	}
}
static int metadata_commit_token(struct httpd_request *request, char out[65])
{
	struct httpd_form_value *value=NULL;
	unsigned int i,count=0;
	if (!request||!out) return -EINVAL;
	for(i=0;i<request->form.count;i++) {
		if(request->form.values[i].name&&!strcmp(request->form.values[i].name,"commit_token")) {
			value=&request->form.values[i];count++;
		}
	}
	if(count!=1||!value||!value->data||value->size!=64||
	   memchr(value->data,0,value->size)) return -EINVAL;
	for(i=0;i<value->size;i++) {
		char c=value->data[i];
		if(!((c>='0'&&c<='9')||(c>='a'&&c<='f'))) return -EINVAL;
		out[i]=c;
	}
	out[64]=0;return 0;
}
static int metadata_upload_target(struct httpd_request *request,
				 upgrade_type_t type,
				 enum rt3_md_target *target,
				 int *explicit_target)
{
	unsigned int i, count = 0;
	(void)type;
	if (!request || !target || !explicit_target) return -EINVAL;
	for (i = 0; i < request->form.count; i++) {
		if (request->form.values[i].name &&
		    !strcmp(request->form.values[i].name, "cdt_target"))
			count++;
	}
	*target = RT3_MD_TARGET_DEFAULT;
	*explicit_target = 0;
	/* CDT always writes both copies; a per-copy cdt_target is refused. */
	return count ? -EINVAL : 0;
}
#endif

void failsafe_upload_invalidate(void)
{
	httpd_upload_buffer_clobbered();
	/* result_handler writes only when upload_data_id == fs_upload_id. */
	upload_data_id = fs_upload_id + 1;
#ifndef CONFIG_H3C_IPQ5018_COMMON
	upload_data_md5_valid = false;
	/* a reboot or INITRAMFS boot queued by a finished /result */
	auto_action_pending = false;
#endif
#ifdef CONFIG_H3C_IPQ5018_COMMON
	rt3_metadata_invalidate();
#endif
#ifdef CONFIG_H3C_RESCUE_INITRAMFS_STAGE
	failsafe_initramfs_invalidate();
#endif
}

static void upload_handler(enum httpd_uri_handler_status status,
        struct httpd_request *request,
        struct httpd_response *response)
{
	struct httpd_form_value *form_value;
	struct upload_session *sess;
	enum rt3_md_target metadata_target = RT3_MD_TARGET_DEFAULT;
#ifdef CONFIG_H3C_IPQ5018_COMMON
	int has_cdt_target;
#endif
	int idx;

	if (status == HTTP_CB_NEW) {
		sess = calloc(1, sizeof(*sess));
		if (!sess) {
			response->info.code = 500;
			return;
		}

		handle_start_led_state();
#ifdef CONFIG_H3C_IPQ5018_COMMON
		rt3_metadata_invalidate();
#endif
#ifdef CONFIG_H3C_RESCUE_INITRAMFS_STAGE
		failsafe_initramfs_invalidate();
#endif

		response->session_data = sess;

		response->status = HTTP_RESP_CUSTOM;

		response->info.http_1_0 = 1;
		response->info.content_length = -1;
		response->info.connection_close = 1;
		response->info.content_type = "application/json";
		response->info.code = 200;

		response->size = http_make_response_header(&response->info,
							sess->header_buf, sizeof(sess->header_buf));

		response->data = sess->header_buf;

		return;
	}

	if (status == HTTP_CB_RESPONDING) {
		sess = response->session_data;

		if (sess->body_sent) {
			response->status = HTTP_RESP_NONE;
			return;
		}

		/* The buffer was reused (slot probe) while this upload was in it. */
		if (request->upload_gen != httpd_upload_buffer_gen()) {
#ifdef CONFIG_H3C_IPQ5018_COMMON
			/* This upload already overwrote the RAM of the previous one. */
			upload_data_id = fs_upload_id + 1;
#endif
			/* Non-H3C: a newer upload may own the RAM and its validated
			 * state now; /result checks the generation before writing, so
			 * this stale request only reports itself. */
			response->data = "{\"status\":\"fail\",\"info\":{\"type\":\"upload_interrupted\"}}";
			response->size = strlen(response->data);
			sess->body_sent = 1;
			sess->ret = RET_FAILURE;
#ifdef CONFIG_H3C_IPQ5018_COMMON
			rt3_metadata_invalidate();
#endif
			return;
		}

		/* new upload session identifier */
		fs_upload_id = rand();

		for (idx = 0; idx < ARRAY_SIZE(upgrade_types); idx++) {
			form_value = httpd_request_find_value(request, upgrade_types[idx].label);
			if (form_value) {
				upgrade_type = upgrade_types[idx].type;
				break;
			}
		}

#ifdef CONFIG_H3C_IPQ5018_COMMON
		if (metadata_upload_target(request, upgrade_type, &metadata_target,
					   &has_cdt_target) ||
		    request->form.count != (u32)(1 + has_cdt_target)) {
			rt3_metadata_invalidate();
#ifdef CONFIG_H3C_RESCUE_INITRAMFS_STAGE
			failsafe_initramfs_invalidate();
#endif
			response->data = "{\"status\":\"fail\",\"info\":{\"type\":\"invalid_upload_fields\"}}";
			response->size = strlen(response->data);
			sess->body_sent = 1;
			return;
		}
#endif

		if (idx == ARRAY_SIZE(upgrade_types)) {
			puts("NO supported upgrade type found!\n");

			/* 没有匹配的 upgrade_type，返回 fail*/
			response->data = "{\"status\":\"fail\","
							"\"info\":{\"type\":\"wrong_upgrade_type\"}}";
			response->size = strlen(response->data);
			sess->body_sent = 1;

			httpd_debug("response message: %s\n", response->data);

			return;
		}

		upload_data_id = fs_upload_id;
		upload_data = form_value->data;
		upload_size = form_value->size;

		httpd_debug("upload_data = 0x%lx, upload_size = %lu (0x%lx)\n",
			(ulong)upload_data, (ulong)upload_size, (ulong)upload_size);

		sess->ret = failsafe_validate_image(upgrade_type, form_value->filename,
						metadata_target, upload_data,
						(ulong)upload_size, response);
#ifndef CONFIG_H3C_IPQ5018_COMMON
		/* Only an image that passed every check may reach /result. */
		if (sess->ret != RET_SUCCESS) {
			upload_data_id = fs_upload_id + 1;
			upload_data_md5_valid = false;
		} else {
			upload_data_gen = request->upload_gen;
			md5((u8 *)upload_data, upload_size, upload_data_md5);
			upload_data_md5_valid = true;
		}
#endif

		sess->body_sent = 1;

		httpd_debug("response message: %s\n", response->data);

		return;
	}

	if (status == HTTP_CB_CLOSED) {
		sess = response->session_data;

		if (sess->ret == RET_SUCCESS)
			handle_success_led_state();
		else
			handle_fail_led_state();

		free(response->session_data);
	}
}


#ifndef CONFIG_H3C_IPQ5018_COMMON
/*
 * Right before /result writes: the shared RAM must not have been claimed by
 * any other upload (or the slot probe) since validation, and the image is
 * validated again in place, which repeats the board check and the 0xff page
 * tail. A failure leaves its JSON in response->data.
 */
static int generic_prewrite_check(struct httpd_request *request,
				  struct httpd_response *response, u32 armed_id)
{
	int ret;

	/* Only the upload that was current when this /result arrived. */
	if (armed_id != upload_data_id) {
		response->data = "{\"status\":\"fail\",\"info\":{\"type\":\"upload_id_mismatch\"}}";
		return RET_FAILURE;
	}
	/* Same bytes as validated, whatever rewrote the RAM since (terminal,
	 * telnet, a command run between two httpd sessions, a download). */
	if (!failsafe_upload_unchanged()) {
		response->data = "{\"status\":\"fail\",\"info\":{\"type\":\"upload_interrupted\"}}";
		return RET_FAILURE;
	}
	ret = failsafe_validate_image(upgrade_type, NULL, RT3_MD_TARGET_DEFAULT,
				      upload_data, (ulong)upload_size, response);
	if (ret == RET_SUCCESS && !failsafe_upload_unchanged()) {
		response->data = "{\"status\":\"fail\",\"info\":{\"type\":\"upload_interrupted\"}}";
		return RET_FAILURE;
	}
	return ret;
}
#endif

static void result_handler(enum httpd_uri_handler_status status,
        struct httpd_request *request,
        struct httpd_response *response)
{
	struct httpd_form_value *auto_reboot;
	struct result_session *st;
	u32 size;

	if (status == HTTP_CB_NEW) {
		st = calloc(1, sizeof(*st));
		if (!st) {
			response->info.code = 500;
			return;
		}

		handle_start_led_state();

		auto_reboot = httpd_request_find_value(request, "auto_reboot");

		if (!auto_reboot || !auto_reboot->data || strcmp(auto_reboot->data, "true"))
			st->auto_reboot = false;
		else
			st->auto_reboot = true;

		st->ret = RET_FAILURE;
		st->gen = httpd_upload_buffer_gen();
#ifndef CONFIG_H3C_IPQ5018_COMMON
		st->armed_id = upload_data_id;
#endif

		response->session_data = st;

		response->status = HTTP_RESP_CUSTOM;

		response->info.http_1_0 = 1;
		response->info.content_length = -1;
		response->info.connection_close = 1;
		response->info.content_type = "application/json";
		response->info.code = 200;

		size = http_make_response_header(&response->info,
			st->buf, sizeof(st->buf));

		response->data = st->buf;
		response->size = size;

		return;
	}

	if (status == HTTP_CB_RESPONDING) {
		st = response->session_data;

		if (st->body_sent) {
			response->status = HTTP_RESP_NONE;
			return;
		}

		if (upload_data_id == fs_upload_id) {
#ifdef CONFIG_H3C_IPQ5018_COMMON
			enum rt3_md_kind kind;
			if (metadata_kind_for_upgrade(upgrade_type,&kind)) {
				char token[65];
				st->auto_reboot = false;
				if (metadata_commit_token(request,token)) {
					st->ret=rt3_metadata_write_target(kind,RT3_MD_TARGET_DEFAULT,NULL,response);
				} else if (upgrade_type == WEBFAILSAFE_UPGRADE_TYPE_CDT) {
					enum rt3_md_target target;
					int explicit_target;
					if (metadata_upload_target(request,upgrade_type,&target,&explicit_target))
						st->ret=rt3_metadata_write_target(kind,RT3_MD_TARGET_DEFAULT,NULL,response);
					else if (explicit_target)
						st->ret=rt3_metadata_write_target(kind,target,token,response);
					else {
#if defined(CONFIG_H3C_METADATA_IMPLICIT_TARGET)
						st->ret=rt3_metadata_write(kind,token,response);
#else
						st->ret=rt3_metadata_write_target(kind,RT3_MD_TARGET_DEFAULT,token,response);
#endif
					}
				} else {
#if defined(CONFIG_H3C_METADATA_IMPLICIT_TARGET)
					st->ret=rt3_metadata_write(kind,token,response);
#else
					st->ret=rt3_metadata_write_target(kind,RT3_MD_TARGET_DEFAULT,token,response);
#endif
				}
			} else
#endif /* CONFIG_H3C_IPQ5018_COMMON */
			{
#ifdef CONFIG_H3C_RESCUE_INITRAMFS_STAGE
				if (upgrade_type == WEBFAILSAFE_UPGRADE_TYPE_INITRAMFS) {
					rt3_metadata_invalidate();
					if (failsafe_initramfs_is_validated((ulong)upload_data,
								    (ulong)upload_size)) {
						st->auto_reboot = true;
						st->ret = RET_SUCCESS;
					} else {
						failsafe_initramfs_invalidate();
						st->auto_reboot = false;
						st->ret = RET_FAILURE;
						strlcpy(st->buf,
							"{\"status\":\"fail\",\"info\":{\"type\":\"initramfs_not_validated\"}}",
							sizeof(st->buf));
						response->data = st->buf;
					}
				} else {
					rt3_metadata_invalidate();
					failsafe_initramfs_invalidate();
					st->auto_reboot = false;
					st->ret=failsafe_write_image(upgrade_type,(ulong)upload_data,
						(ulong)upload_size,response);
				}
#else
#ifndef CONFIG_H3C_IPQ5018_COMMON
				st->ret = generic_prewrite_check(request, response, st->armed_id);
				if (st->ret != RET_SUCCESS)
					st->auto_reboot = false;
				else
#endif
				if (upgrade_type == WEBFAILSAFE_UPGRADE_TYPE_INITRAMFS) {
					st->auto_reboot = true;
					st->ret = RET_SUCCESS;
				} else {
					st->ret=failsafe_write_image(upgrade_type,(ulong)upload_data,
						(ulong)upload_size,response);
				}
#endif
			}
		} else {
			snprintf(st->buf, sizeof(st->buf),
				"{\"status\":\"fail\","
				"\"info\":{\"type\":\"upload_id_mismatch\","
				"\"upload_data_id\":\"%u\",\"fs_upload_id\":\"%u\"}}",
				upload_data_id, fs_upload_id);
			response->data = st->buf;
			st->ret = RET_UPLOAD_ID_MISMATCH;
#ifdef CONFIG_H3C_IPQ5018_COMMON
			rt3_metadata_invalidate();
#endif
#ifdef CONFIG_H3C_RESCUE_INITRAMFS_STAGE
			failsafe_initramfs_invalidate();
#endif
		}

#ifdef CONFIG_H3C_IPQ5018_COMMON
		/* Headers were already streamed; preserve the custom body lifecycle
		 * even when a metadata helper formats a standard error response. */
		response->status = HTTP_RESP_CUSTOM;
#endif

		/* invalidate upload identifier */
		upload_data_id = rand();

		if (st->ret == RET_SUCCESS) {
			snprintf(st->buf, sizeof(st->buf),
				"{\"status\":\"success\",\"info\":{\"reboot\":%s}}",
				st->auto_reboot ? "true" : "false");
			response->data = st->buf;
		}

		response->size = strlen(response->data);
		st->body_sent = 1;

		httpd_debug("response message: %s\n", response->data);

		return;
	}

	if (status == HTTP_CB_CLOSED) {
		bool upgrade_success;

		st = response->session_data;
		/* A RAM boot or reset must not follow if the buffer was reused. */
		upgrade_success = st->ret == RET_SUCCESS &&
				  st->gen == httpd_upload_buffer_gen();
		auto_action_pending = st->auto_reboot && upgrade_success;

		free(response->session_data);

		if (upgrade_success)
			handle_success_led_state();
		else
			handle_fail_led_state();

		if (auto_action_pending)
			tcp_close_all_conn();
	}
}



void upgrade_register_uri_handlers(struct httpd_instance *inst)
{
	httpd_register_uri_handler(inst, "/upload", &upload_handler, NULL);
	httpd_register_uri_handler(inst, "/result", &result_handler, NULL);
#ifdef CONFIG_H3C_IPQ5018_COMMON
	/* Metadata commits are token-gated in the result handler. */
	httpd_register_uri_handler(inst, "/write", &result_handler, NULL);
#endif
}
