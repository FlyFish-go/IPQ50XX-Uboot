#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <h3c_nand_auto.h>

/* Fake flash: for every (mode) a page table; offset -> content class. */
struct fake {
	unsigned int mode, spare;
	int content[2][5];	/* [mode==8][page idx]: 0 blank,1 valid,2 ecc err,3 junk(valid-looking ECC but wrong magic) */
	int hard_error_mode;	/* read returns -5 in this mode (0: none) */
	int set_fail_mode;
	unsigned int sets[16], nsets, spares[16];
	unsigned char buf[H3C_NAND_AUTO_PAGE_BYTES];
};

static void fill_valid(unsigned int kind, unsigned char *p)
{
	static const unsigned char sbl1[8] = { 0xd1, 0xdc, 0x4b, 0x84, 0x34, 0x10, 0xd7, 0x73 };
	static const unsigned char elf[4] = { 0x7f, 'E', 'L', 'F' };
	static const unsigned char mib[8] = { 0xac, 0x9f, 0x56, 0xfe, 0x7a, 0x12, 0x7f, 0xcd };
	static const unsigned char pt[8] = { 0xaa, 0x73, 0xee, 0x55, 0xdb, 0xbd, 0x5e, 0xe3 };

	memset(p, 0x5a, H3C_NAND_AUTO_PAGE_BYTES);
	if (kind == H3C_NAND_AUTO_KIND_SBL1) memcpy(p, sbl1, 8);
	else if (kind == H3C_NAND_AUTO_KIND_ELF) memcpy(p, elf, 4);
	else if (kind == H3C_NAND_AUTO_KIND_MIBIB_HDR) memcpy(p, mib, 8);
	else memcpy(p, pt, 8);
}

static int t_set(void *ctx, unsigned int bits, unsigned int spare)
{
	struct fake *f = ctx;

	if (f->set_fail_mode == (int)bits)
		return -1;
	f->mode = bits; f->spare = spare;
	f->sets[f->nsets] = bits; f->spares[f->nsets++] = spare;
	return 0;
}

static int t_read(void *ctx, unsigned long long off, unsigned char *buf, unsigned int len)
{
	struct fake *f = ctx;
	unsigned int i;

	for (i = 0; i < h3c_nand_auto_page_count; i++)
		if (h3c_nand_auto_pages[i].offset == off)
			break;
	assert(i < h3c_nand_auto_page_count && len == H3C_NAND_AUTO_PAGE_BYTES);
	if (f->hard_error_mode == (int)f->mode)
		return -5;
	switch (f->content[f->mode == 8][i]) {
	case 0: memset(buf, 0xff, len); return 0;
	case 1: fill_valid(h3c_nand_auto_pages[i].kind, buf); return 0;
	case 2: return H3C_NAND_AUTO_READ_ECC;
	default: memset(buf, 0x11, len); return 0;
	}
}

static struct h3c_nand_auto_ops ops_for(struct fake *f)
{
	struct h3c_nand_auto_ops o = { f, t_set, t_read, f->buf, sizeof(f->buf) };
	return o;
}

static const unsigned char GD[2] = { 0xc8, 0x41 };
static const unsigned char FM[2] = { 0xa1, 0xa5 };

static void set_all(struct fake *f, int m4, int m8)
{
	int i;
	for (i = 0; i < 5; i++) { f->content[0][i] = m4; f->content[1][i] = m8; }
}

int main(void)
{
	struct fake f;
	struct h3c_nand_auto_ops o;
	struct h3c_nand_auto_result r;
	unsigned char id[2] = { 0xef, 0xba };

	/* page validity primitives */
	{
		unsigned char p[H3C_NAND_AUTO_PAGE_BYTES];
		memset(p, 0xff, sizeof(p));
		assert(!h3c_nand_auto_page_valid(H3C_NAND_AUTO_KIND_ELF, p, sizeof(p)));
		fill_valid(H3C_NAND_AUTO_KIND_ELF, p);
		assert(h3c_nand_auto_page_valid(H3C_NAND_AUTO_KIND_ELF, p, sizeof(p)));
		assert(!h3c_nand_auto_page_valid(H3C_NAND_AUTO_KIND_MIBIB_HDR, p, sizeof(p)));
		fill_valid(H3C_NAND_AUTO_KIND_SBL1, p);
		assert(h3c_nand_auto_page_valid(H3C_NAND_AUTO_KIND_SBL1, p, sizeof(p)));
		assert(!h3c_nand_auto_page_valid(H3C_NAND_AUTO_KIND_ELF, p, sizeof(p)));
	}

	/* 1. unique id: one row, one mode, no probe, no flash access */
	memset(&f, 0, sizeof(f)); o = ops_for(&f);
	assert(h3c_nand_auto_resolve(id, "W25N01GWZEIG", &o, &r) == 0);
	assert(r.row && !strcmp(r.row->profile_id, "h3c-oem-efba-128m-2k-sp64"));
	assert(r.mode == 4 && r.spare == 64 && !r.probed && f.nsets == 0);
	/* wrong model name for the id is not a match */
	assert(h3c_nand_auto_resolve(id, "W25N01JW", &o, &r) == H3C_NAND_AUTO_E_NOROW);
	assert(!r.row);
	{ unsigned char bad[2] = { 0x12, 0x34 };
	  assert(h3c_nand_auto_resolve(bad, "X", &o, &r) == H3C_NAND_AUTO_E_NOROW); }
	/* ambiguous chip without ops needs a probe */
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", NULL, &r) == H3C_NAND_AUTO_E_NEED_PROBE);
	assert(h3c_nand_auto_resolve_catalog(GD, "GD5F1GQ5REYIG", &r) == H3C_NAND_AUTO_E_NEED_PROBE);

	/* 2. GD5F1GQ5REYIG with only ECC4 evidence */
	memset(&f, 0, sizeof(f)); o = ops_for(&f);
	set_all(&f, 1, 2);
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == 0);
	assert(r.mode == 4 && r.probed && r.spare == 128 && r.valid4 == 5 && r.valid8 == 0);
	assert(f.mode == 4);	/* controller left in the selected format */

	/* 3. only ECC8 evidence (blank in ECC4 is fine, junk is not evidence) */
	memset(&f, 0, sizeof(f)); o = ops_for(&f);
	set_all(&f, 3, 1);
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == 0);
	assert(r.mode == 8 && f.mode == 8);

	/* 4. blank under both: unknown */
	memset(&f, 0, sizeof(f)); o = ops_for(&f); set_all(&f, 0, 0);
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == H3C_NAND_AUTO_E_UNKNOWN);
	assert(!r.row);

	/* 5. valid under both: unknown */
	memset(&f, 0, sizeof(f)); o = ops_for(&f); set_all(&f, 1, 1);
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == H3C_NAND_AUTO_E_UNKNOWN);

	/* 6. one evidence page only: unknown */
	memset(&f, 0, sizeof(f)); o = ops_for(&f); set_all(&f, 0, 2);
	f.content[0][3] = 1;
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == H3C_NAND_AUTO_E_UNKNOWN);
	/* two pages in one mode but a stray valid page in the other: unknown */
	set_all(&f, 0, 2);
	f.content[0][0] = f.content[0][3] = 1; f.content[1][4] = 1;
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == H3C_NAND_AUTO_E_UNKNOWN);
	/* exactly two pages is enough */
	set_all(&f, 0, 2);
	f.content[0][1] = f.content[0][2] = 1;
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == 0 && r.mode == 4);
	/* wrong magic in the right place is not evidence */
	set_all(&f, 3, 3);
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == H3C_NAND_AUTO_E_UNKNOWN);

	/* 7. hard read error / controller switch failure: unknown */
	memset(&f, 0, sizeof(f)); o = ops_for(&f); set_all(&f, 1, 2);
	f.hard_error_mode = 8;
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == H3C_NAND_AUTO_E_IO);
	assert(!r.row);
	f.hard_error_mode = 0; f.set_fail_mode = 4;
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == H3C_NAND_AUTO_E_IO);
	f.set_fail_mode = 8;
	assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &o, &r) == H3C_NAND_AUTO_E_IO);
	{ struct h3c_nand_auto_ops bad = o; bad.buf = NULL;
	  assert(h3c_nand_auto_resolve(GD, "GD5F1GQ5REYIG", &bad, &r) == H3C_NAND_AUTO_E_NEED_PROBE); }

	/* 8. FM25LS01: two rows, ECC4 uses spare 64, ECC8 uses spare 128 */
	memset(&f, 0, sizeof(f)); o = ops_for(&f); set_all(&f, 1, 2);
	assert(h3c_nand_auto_resolve(FM, "FM25LS01", &o, &r) == 0);
	assert(r.mode == 4 && r.spare == 64 && r.probed);
	assert(!strcmp(r.row->profile_id, "h3c-oem-a1a5-128m-2k-sp64-p2048-e131072"));
	assert(f.nsets == 3 && f.sets[0] == 4 && f.spares[0] == 64 &&
	       f.sets[1] == 8 && f.spares[1] == 128 &&
	       f.sets[2] == 4 && f.spares[2] == 64);
	memset(&f, 0, sizeof(f)); o = ops_for(&f); set_all(&f, 2, 1);
	assert(h3c_nand_auto_resolve(FM, "FM25LS01", &o, &r) == 0);
	assert(r.mode == 8 && r.spare == 128);
	assert(!strcmp(r.row->profile_id, "h3c-oem-a1a5-128m-2k-sp128-p2048-e131072"));
	assert(f.mode == 8 && f.spare == 128);
	memset(&f, 0, sizeof(f)); o = ops_for(&f); set_all(&f, 0, 0);
	assert(h3c_nand_auto_resolve(FM, "FM25LS01", &o, &r) == H3C_NAND_AUTO_E_UNKNOWN);

	/* every catalog chip is either decided by the catalog or probed */
	{
		unsigned int i, probe = 0, uniq = 0;
		for (i = 0; i < H3C_NAND_CATALOG_PROFILE_COUNT; i++) {
			const struct h3c_nand_catalog_profile *p = &h3c_nand_catalog_profiles[i];
			int ret = h3c_nand_auto_resolve_catalog(p->id, p->qpic_model, &r);
			if (ret == H3C_NAND_AUTO_E_NEED_PROBE) probe++;
			else if (ret == 0) { uniq++; assert(!strcmp(r.row->profile_id, p->profile_id)); }
		}
		assert(probe == 3);	/* c841 once, a1a5 twice */
		printf("catalog rows: %u unique, %u need probe\n", uniq, probe);
	}
	puts("PASS");
	return 0;
}
