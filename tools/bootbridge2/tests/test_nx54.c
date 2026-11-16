// SPDX-License-Identifier: GPL-2.0-or-later
/* Private inputs stay external: NX54_RAW, BB_PACK and BB_NX54_TEST_OUT.
 * No device IO. MIBIB provides the offsets for every simulated partition. */
#include "../runtime/layout.h"
#include "../runtime/install.h"
#include "../runtime/backup.h"
#include "../runtime/pack.h"
#include "../runtime/sha256.h"
#include "flash_mem.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks, failures;
#define CHECK(c, msg) do { checks++; if (!(c)) { failures++; printf("FAIL %u: %s\n", __LINE__, msg); } } while (0)
#define REQUIRE(c, msg) do { int pass = !!(c); CHECK(pass, msg); if (!pass) exit(1); } while (0)
static struct mem_nand *parts[20];
static uint8_t *original[20];
static struct bb_part_spec specs[32];
static const struct bb_layout *layout;
static struct bb_inst_inputs in;

static uint32_t le32(const uint8_t *p)
{
	return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24;
}

static uint32_t be32(const uint8_t *p)
{
	return (uint32_t)p[0] << 24 | p[1] << 16 | p[2] << 8 | p[3];
}

static void put32(uint8_t *p, uint32_t v)
{
	for (unsigned i = 0; i < 4; i++) p[i] = v >> (8 * i);
}

static uint8_t *load(const char *path, size_t *size)
{
	FILE *f = fopen(path, "rb");
	if (!f) return NULL;
	fseek(f, 0, SEEK_END);
	long n = ftell(f);
	rewind(f);
	uint8_t *p = n < 0 ? NULL : malloc((size_t)n + 1);
	if (p && fread(p, 1, n, f) != (size_t)n) { free(p); p = NULL; }
	fclose(f);
	if (p) { p[n] = 0; *size = n; }
	return p;
}

static void hexhash(const uint8_t *p, size_t n, char out[65])
{
	struct bb_sha256 s;
	uint8_t d[32];
	bb_sha256_init(&s); bb_sha256_update(&s, p, n); bb_sha256_final(&s, d); bb_sha256_hex(d, out);
}

static void rig(void)
{
	char path[4096];
	size_t n;
	snprintf(path, sizeof(path), "%s/mtd1-MIBIB.a.bin", getenv("NX54_RAW"));
	uint8_t *m = load(path, &n);
	REQUIRE(m && n == 0x80000, "MIBIB input");
	REQUIRE(le32(m) == 0xfe569fac && le32(m + 4) == 0xcd7f127a &&
		le32(m + 2048) == 0x55ee73aa && le32(m + 2052) == 0xe35ebddb &&
		le32(m + 2056) == 4 && le32(m + 2060) == 20, "real MIBIB headers/count");
	for (unsigned i = 0; i < 20; i++) {
		const uint8_t *e = m + 2064 + i * 28;
		char name[17];
		memcpy(name, e, 16); name[16] = 0;
		const char *file = !strncmp(name, "0:", 2) ? name + 2 : name;
		snprintf(path, sizeof(path), "%s/mtd%u-%s.a.bin", getenv("NX54_RAW"), i, file);
		original[i] = load(path, &n);
		REQUIRE(original[i] && n == (size_t)le32(e + 20) * 0x20000, "partition dump size agrees with MIBIB");
		parts[i] = mem_nand_new(name, le32(e + 16) * 0x20000, n, original[i]);
		REQUIRE(parts[i], "simulated NAND allocated");
	}
	free(m);
	layout = bb_layout_slots(&parts[15]->f, &parts[16]->f);
	REQUIRE(layout && !strcmp(layout->id, "nx54") && layout->full_backup, "NX54 slot layout");
	REQUIRE(bb_layout_backup(layout, specs, 32) == 20, "full backup has exactly 20 required partitions");
	for (unsigned i = 0; i < 20; i++) {
		CHECK(!strcmp(specs[i].name, parts[i]->f.name), "backup partition name agrees with MIBIB");
		CHECK(bb_part_matches(&specs[i], &parts[i]->f) && !specs[i].optional, "backup extent agrees with MIBIB and is required");
	}
	for (unsigned i = 0; i < 2; i++) {
		in.appsbl[i] = &parts[11 + i]->f;
		in.ret.bc[i] = &parts[2 + i]->f;
		in.ret.slot[i] = &parts[15 + i]->f;
	}
	in.ret.running_offset = layout->slot_offset[1];
}

static struct bb_facts facts(void)
{
	struct bb_facts f = {0};
	CHECK(!bb_facts_parse_dt_model(&f, "Qualcomm Technologies, Inc. IPQ5018/AP-MP03.1"), "stock DT route");
	CHECK(!bb_facts_parse_cdt(&f, original[8], parts[8]->f.size) && f.machid == 0x08040001, "real CDT machid");
	CHECK(!bb_facts_parse_env(&f, original[10], parts[10]->f.size) && !strcmp(f.productname, "NX54"), "real ENV CRC/product");
	CHECK(!bb_facts_parse_kmsg(&f,
		"nand: device found, Manufacturer ID: 0xc8, Chip ID: 0x11\n"
		"nand: GigaDevice F50D1G41LB(2M) SPI NAND 1G 1.8V\n"
		"nand: 128 MiB, SLC, erase size: 128 KiB, page size: 2048, OOB size: 64\n"), "OEM kernel NAND model string and observed geometry");
	f.mtd_ecc_strength = 4; f.mtd_oob = 64;
	snprintf(f.layout, sizeof(f.layout), "%s", layout->id);
	hexhash(original[0], parts[0]->f.size, f.sbl1_sha256);
	return f;
}

static void identify(const struct bb_rules *r, struct bb_facts base)
{
	struct bb_decision d;
	bb_rules_decide(r, &base, &d);
	CHECK(d.code == BB_DEC_OK && !strcmp(d.board, "NX54"), "NX54 positively identified");
	for (unsigned i = 0; i < 9; i++) {
		struct bb_facts f = base;
		switch (i) {
		case 0: snprintf(f.productname, sizeof(f.productname), "BX54E"); break;
		case 1: snprintf(f.productname, sizeof(f.productname), "UNKNOWN"); break;
		case 2: f.env_crc_ok = 0; break;
		case 3: f.sbl1_sha256[0] ^= 1; break;
		case 4: f.sbl1_sha256[0] = 0; break;
		case 5: f.machid++; break;
		case 6: f.have_route = 0; break;
		case 7: f.layout[0] = 0; break;
		case 8: snprintf(f.productname, sizeof(f.productname), "NX30"); break;
		}
		bb_rules_decide(r, &f, &d);
		CHECK(d.code == BB_DEC_NO_BOARD && !d.cand, "unknown NX54 identity cannot fall through to HW-A");
	}
	struct bb_facts f = base;
	f.nand_chip = 0x99;
	bb_rules_decide(r, &f, &d);
	CHECK(d.code == BB_DEC_NO_NAND, "unknown NX54 NAND refused");
	f = base; f.mtd_ecc_strength = 8;
	bb_rules_decide(r, &f, &d);
	CHECK(d.code == BB_DEC_NO_CANDIDATE, "unqualified NX54 ECC refused");
}

static void reset_boot(unsigned running, unsigned active)
{
	in.ret.running_offset = layout->slot_offset[running];
	for (unsigned c = 0; c < 2; c++) {
		struct mem_nand *m = parts[2 + c];
		memcpy(m->data, original[2 + c], m->f.size);
		memset(m->bad, 0, m->f.size / m->f.erase_size);
		m->fail_write_at = m->fail_erase_at = 0;
		struct bb_bc bc;
		REQUIRE(bb_bc_parse(m->data, m->f.size, &bc) == BB_BC_OK, "real BOOTCONFIG parses");
		bb_bc_set(m->data, &bc, running, bc.age);
		for (unsigned i = 0; i < bc.count; i++)
			if (!strcmp((char *)m->data + 12 + 20 * i, "0:APPSBL"))
				put32(m->data + 28 + 20 * i, active);
	}
	for (unsigned c = 0; c < 2; c++) {
		struct mem_nand *m = parts[11 + c];
		memcpy(m->data, original[11 + c], m->f.size);
		m->fail_write_at = m->fail_erase_at = 0;
	}
}

static void returns(void)
{
	for (unsigned running = 0; running < 2; running++) {
		reset_boot(running, 0);
		struct bb_ret_plan p;
		bb_ret_plan(&in.ret, &p);
		REQUIRE(p.code == BB_RET_READY, "OEM return accepts real NX54 rootfs/BOOTCONFIG in either slot");
		CHECK(p.target_selector == !running && p.oem_offset == layout->slot_offset[!running], "selector follows physical offset");
		CHECK(bb_ret_commit(&in.ret, &p) == BB_RET_DONE, "OEM return commits");
		for (unsigned c = 0; c < 2; c++) {
			CHECK(!memcmp(parts[2+c]->data, p.updated[c], parts[2+c]->f.erase_size), "BOOTCONFIG readback equals planned image");
			CHECK(!memcmp(parts[2+c]->data + parts[2+c]->f.erase_size,
				original[2+c] + parts[2+c]->f.erase_size, parts[2+c]->f.erase_size), "BOOTCONFIG second eraseblock preserved");
		}
		bb_ret_plan_free(&p);
	}
	for (unsigned mode = 0; mode < 4; mode++) {
		reset_boot(1, 0);
		struct bb_ret_plan p;
		if (mode == 0) parts[2]->data[0] ^= 1;
		if (mode == 1) parts[3]->data[0] ^= 1;
		if (mode == 2) parts[2]->data[0] ^= 1, parts[3]->data[0] ^= 1;
		if (mode == 3) parts[3]->bad[0] = 1;
		bb_ret_plan(&in.ret, &p);
		CHECK(mode < 2 ? p.code == BB_RET_READY : p.code != BB_RET_READY, "one invalid BC rebuilt; both invalid or bad BC block refused");
		if (mode < 2) CHECK(bb_ret_commit(&in.ret, &p) == BB_RET_DONE, "rebuild invalid BOOTCONFIG");
		bb_ret_plan_free(&p);
	}
	reset_boot(1, 0);
	struct bb_ret_plan p;
	bb_ret_plan(&in.ret, &p);
	parts[3]->fail_erase_at = parts[3]->erases + 1;
	CHECK(bb_ret_commit(&in.ret, &p) == BB_RET_WRITE_BC1 &&
		!memcmp(parts[2]->data, p.image[0], parts[2]->f.size / 2), "BC1 failure leaves primary intact");
	bb_ret_plan_free(&p);
	reset_boot(1, 0);
	unsigned corrupt = 0;
	for (unsigned off = 0; off < parts[15]->f.size; off += 0x20000) {
		const uint8_t *x = parts[15]->data + off;
		if (!memcmp(x, "UBI#", 4) && !memcmp(x + 2048, "UBI!", 4) && !be32(x + 2056)) {
			corrupt = off + 4096;
			break;
		}
	}
	REQUIRE(corrupt, "locate real kernel volume payload for CRC failure");
	parts[15]->data[corrupt] ^= 1;
	bb_ret_plan(&in.ret, &p);
	CHECK(p.code == BB_RET_OEM_SLOT, "corrupt OEM UBI refused");
	bb_ret_plan_free(&p);
	parts[15]->data[corrupt] ^= 1;
}

static void installs(const struct bb_candidate *c, const uint8_t *mbn, size_t bytes)
{
	for (unsigned active = 0; active < 2; active++) {
		for (unsigned failure = 0; failure < 3; failure++) {
			reset_boot(1, active);
			struct bb_inst_plan p;
			bb_inst_plan(&in, c, mbn, bytes, &p);
			REQUIRE(p.code == BB_INST_READY, "NX54 install plan ready");
			CHECK(p.first == (int)!active && p.second == (int)active, "inactive APPSBL written first for either selector");
			if (failure) {
				unsigned idx = 11 + (failure == 1 ? !active : active);
				parts[idx]->fail_erase_at = parts[idx]->erases + 1;
			}
			enum bb_inst_code rc = bb_inst_commit(&in, &p);
			CHECK(rc == (failure == 0 ? BB_INST_DONE : failure == 1 ? BB_INST_WRITE_FIRST : BB_INST_WRITE_SECOND), "install success and first/second copy failures");
			if (!failure) {
				for (unsigned i = 0; i < 2; i++)
					CHECK(!memcmp(parts[11+i]->data, p.image, p.image_len), "both complete APPSBL readback incl 0xff tail");
				for (unsigned i = 0; i < 2; i++) {
					struct bb_bc bc;
					CHECK(bb_bc_parse(parts[2+i]->data, parts[2+i]->f.size, &bc) == BB_BC_OK &&
						bc.rootfs_selector == 0 && bc.appsbl_selector == active &&
						bc.age == p.ret.new_age, "last step selects OEM rootfs and preserves APPSBL selector");
				}
			} else {
				for (unsigned i = 0; i < 2; i++)
					CHECK(!memcmp(parts[2+i]->data, p.ret.image[i], parts[2+i]->f.erase_size), "BOOTCONFIG unchanged on APPSBL failure");
				if (failure == 1) CHECK(!memcmp(parts[11+active]->data, original[11+active], p.image_len), "inactive failure preserves active APPSBL");
				else CHECK(!memcmp(parts[11+!active]->data, p.image, p.image_len), "second failure preserves verified first APPSBL");
			}
			bb_inst_plan_free(&p);
		}
	}
	reset_boot(1, 0);
	struct bb_candidate wrong = *c;
	snprintf(wrong.board, sizeof(wrong.board), "A");
	struct bb_inst_plan p;
	bb_inst_plan(&in, &wrong, mbn, bytes, &p);
	CHECK(p.code == BB_INST_PARTITIONS, "even old rules cannot install NX30 HW-A on NX54 geometry");
	bb_inst_plan_free(&p);
	parts[11]->f.offset += 0x20000;
	bb_inst_plan(&in, c, mbn, bytes, &p);
	CHECK(p.code == BB_INST_PARTITIONS, "incorrect APPSBL extent refused");
	bb_inst_plan_free(&p);
	parts[11]->f.offset -= 0x20000;
	parts[12]->bad[1] = 1;
	bb_inst_plan(&in, c, mbn, bytes, &p);
	CHECK(p.code == BB_INST_BAD_BLOCK, "APPSBL bad block refused");
	bb_inst_plan_free(&p); parts[12]->bad[1] = 0;
	/* Return remains independent after identification/installation failure. */
	struct bb_ret_plan ret;
	bb_ret_plan(&in.ret, &ret);
	CHECK(ret.code == BB_RET_READY && bb_ret_commit(&in.ret, &ret) == BB_RET_DONE, "independent return after install refusal");
	bb_ret_plan_free(&ret);
}

static void backup(void)
{
	struct bb_backup_entry entries[20];
	struct bb_backup_result result;
	for (unsigned i = 0; i < 20; i++) {
		if (i != 2 && i != 3 && i != 11 && i != 12)
			CHECK(!memcmp(parts[i]->data, original[i], parts[i]->f.size), "return/install never changed another partition");
		memcpy(parts[i]->data, original[i], parts[i]->f.size);
		entries[i].part = &parts[i]->f; entries[i].role = specs[i].role;
		if (!strcmp(specs[i].role, "startup"))
			snprintf(entries[i].file, sizeof(entries[i].file), "startup_%06x.bin", specs[i].offset);
		else snprintf(entries[i].file, sizeof(entries[i].file), "%s.bin", specs[i].name);
	}
	const char *path = getenv("BB_NX54_TEST_OUT");
	REQUIRE(path, "BB_NX54_TEST_OUT must name a private output ZIP");
	FILE *f = fopen(path, "w+b");
	REQUIRE(f, "backup output opens");
	CHECK(!bb_backup_write(f, entries, 20, &result) && result.entries == 21 &&
		result.bytes > 0x7680000 && !result.bad_blocks && !result.unreadable_blocks, "full NX54 backup incl both slots");
	CHECK(!bb_backup_verify(f, &result), "complete backup re-read size/SHA256");
	fclose(f);
}

int main(void)
{
	setvbuf(stdout, NULL, _IONBF, 0);
	if (!getenv("NX54_RAW") || !*getenv("NX54_RAW")) { puts("NX54 test skipped (NX54_RAW unset)"); return 0; }
	REQUIRE(getenv("BB_PACK"), "BB_PACK must contain NX54");
	rig();
	size_t bytes;
	uint8_t *data = load(getenv("BB_PACK"), &bytes);
	struct bb_pack pack;
	REQUIRE(data && bb_pack_open(data, bytes, &pack) == BB_PACK_OK, "NX54 rule pack integrity");
	char *text = strndup(pack.rules, pack.rules_len);
	struct bb_rules rules;
	REQUIRE(!bb_rules_load(&rules, text, NULL), "NX54 rules parse");
	struct bb_facts f = facts();
	identify(&rules, f);
	struct bb_decision d;
	bb_rules_decide(&rules, &f, &d);
	REQUIRE(d.code == BB_DEC_OK && d.cand, "NX54 candidate present");
	uint8_t *mbn = NULL; size_t mbn_len;
	REQUIRE(bb_pack_extract(&pack, d.cand->file, &mbn, &mbn_len) == BB_PACK_OK, "NX54 MBN extracted");
	returns(); installs(d.cand, mbn, mbn_len); backup();
	bb_rules_free(&rules); free(text); free(mbn); free(data);
	for (unsigned i = 0; i < 20; i++) { free(original[i]); mem_nand_free(parts[i]); }
	printf("NX54: %u checks, %u failures\n", checks, failures);
	return failures != 0;
}
