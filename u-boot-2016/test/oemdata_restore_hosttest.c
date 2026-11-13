/* Host test for include/oemdata_restore.h */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <oemdata_restore.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)

static const struct oemdata_smem none = { 0, 0, 0 };

int main(void)
{
	const struct oemdata_part *p;
	struct oemdata_window w;
	struct oemdata_smem named, root;
	size_t i;

	/* file names: the backup page's smem_<name>.bin and plain <name>.bin */
	CHECK((p = oemdata_find("smem_pdt_data.bin")) && !strcmp(p->name, "pdt_data"));
	CHECK((p = oemdata_find("smem_pdt_data_1.bin")) && !strcmp(p->name, "pdt_data_1"));
	CHECK((p = oemdata_find("exp.bin")) && !strcmp(p->name, "exp"));
	CHECK((p = oemdata_find("C:\\backup\\plugin.bin")) && !strcmp(p->name, "plugin"));
	CHECK((p = oemdata_find("/tmp/x/pdt_data.2.bin")) && !strcmp(p->name, "pdt_data"));
	CHECK(!oemdata_find(NULL));
	CHECK(!oemdata_find(""));
	CHECK(!oemdata_find("pdt_data"));		/* no extension */
	CHECK(!oemdata_find("pdt_data.img"));
	CHECK(!oemdata_find("pdt_data.bin.exe"));
	CHECK(!oemdata_find("pdt.bin"));
	CHECK(!oemdata_find("pdt_data_2.bin"));
	CHECK(!oemdata_find("pdt_data1.bin"));
	CHECK(!oemdata_find("raw_pdt_data.bin"));	/* raw: backups are not partitions */
	CHECK(!oemdata_find("smem_rootfs.bin"));
	CHECK(!oemdata_find("smem_exp_old.bin"));
	CHECK(!oemdata_find("smem_.bin"));
	CHECK(!oemdata_find(".bin"));
	CHECK(!oemdata_find("smem_exp/.bin"));
	/* no name can resolve to a different partition */
	for (i = 0; i < OEMDATA_NPARTS; i++) {
		char f[64];
		snprintf(f, sizeof(f), "smem_%s.bin", oemdata_parts[i].name);
		CHECK(oemdata_find(f) == &oemdata_parts[i]);
	}
	/* the table is the OEM table: the four extents do not overlap and end at the XL rootfs end */
	CHECK(oemdata_parts[0].off + oemdata_parts[0].size == oemdata_parts[1].off);
	CHECK(oemdata_parts[1].off + oemdata_parts[1].size == oemdata_parts[2].off);
	CHECK(oemdata_parts[2].off + oemdata_parts[2].size == oemdata_parts[3].off);
	CHECK(oemdata_parts[3].off + oemdata_parts[3].size == OEMDATA_XL_ROOTFS_OFF + OEMDATA_XL_ROOTFS_SIZE);

	/* named partitions (OEM dual or 80 MiB layout): exact extent only */
	named = (struct oemdata_smem){ 1, 0x05900000ULL, 0x00600000ULL };
	root = (struct oemdata_smem){ 1, 0x900000ULL, 0x2800000ULL };
	CHECK(oemdata_window(&oemdata_parts[0], &named, &root, 0, &w) == OEMDATA_OK);
	CHECK(!strcmp(w.name, "pdt_data") && w.off == 0x5900000ULL && w.size == 0x600000ULL);
	named.size = 0x00500000ULL;
	CHECK(oemdata_window(&oemdata_parts[0], &named, &root, 0, &w) == OEMDATA_EXDEV);
	named = (struct oemdata_smem){ 1, 0x05f00000ULL, 0x00600000ULL };
	CHECK(oemdata_window(&oemdata_parts[0], &named, &root, 0, &w) == OEMDATA_EXDEV);	/* wrong place */
	CHECK(oemdata_window(&oemdata_parts[1], &named, &root, 0, &w) == OEMDATA_OK);
	/* a named entry wins even in a single layout (80 MiB with the OEM parts) */
	root = (struct oemdata_smem){ 1, 0x900000ULL, 0x5000000ULL };
	CHECK(oemdata_window(&oemdata_parts[1], &named, &root, 1, &w) == OEMDATA_OK && !strcmp(w.name, "pdt_data_1"));

	/* XL layout: no named entry, the write goes through the exact rootfs window */
	root = (struct oemdata_smem){ 1, 0x900000ULL, 0x7400000ULL };
	for (i = 0; i < OEMDATA_NPARTS; i++) {
		CHECK(oemdata_window(&oemdata_parts[i], &none, &root, 1, &w) == OEMDATA_OK);
		CHECK(!strcmp(w.name, "rootfs") && w.off == 0x900000ULL && w.size == 0x7400000ULL);
		CHECK(oemdata_parts[i].off >= w.off && oemdata_parts[i].off + oemdata_parts[i].size <= w.off + w.size);
	}
	/* anything else is refused: dual without the entries, other rootfs sizes, no rootfs */
	root = (struct oemdata_smem){ 1, 0x900000ULL, 0x2800000ULL };
	CHECK(oemdata_window(&oemdata_parts[0], &none, &root, 0, &w) == OEMDATA_EXDEV);
	CHECK(oemdata_window(&oemdata_parts[0], &none, &root, 1, &w) == OEMDATA_EXDEV);
	root = (struct oemdata_smem){ 1, 0x900000ULL, 0x5000000ULL };
	CHECK(oemdata_window(&oemdata_parts[3], &none, &root, 1, &w) == OEMDATA_EXDEV);
	root = (struct oemdata_smem){ 1, 0x980000ULL, 0x7400000ULL };
	CHECK(oemdata_window(&oemdata_parts[3], &none, &root, 1, &w) == OEMDATA_EXDEV);
	CHECK(oemdata_window(&oemdata_parts[3], &none, &none, 1, &w) == OEMDATA_EXDEV);
	root = (struct oemdata_smem){ 1, 0x900000ULL, 0x7400000ULL };
	CHECK(oemdata_window(&oemdata_parts[3], &none, &root, 0, &w) == OEMDATA_EXDEV);	/* dual flag */
	CHECK(oemdata_window(NULL, &none, &root, 1, &w) == OEMDATA_EXDEV);

	puts("OEMDATA_RESTORE_HOSTTEST_PASS");
	return 0;
}
