/* Host test for the UBI page plan (include/ubi_trimffs.h). */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <ubi_trimffs.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)

#define WS 8
#define ES 32		/* 4 pages per block */
#define NB 8

struct t {
	uint8_t bad[NB];
	uint64_t phys[64]; size_t off[64]; uint32_t n[64]; int wr[64];
	int cnt, fail_at;
};
static int isbad(void *c, uint32_t b) { return ((struct t *)c)->bad[b]; }
static int emit(void *c, uint64_t p, size_t o, uint32_t n, int w)
{
	struct t *t = c;
	if (t->cnt == t->fail_at) return 5;
	t->phys[t->cnt] = p; t->off[t->cnt] = o; t->n[t->cnt] = n; t->wr[t->cnt] = w;
	t->cnt++;
	return 0;
}
static int run(struct t *t, const uint8_t *img, size_t len, struct ubi_trimffs_stats *s)
{
	t->cnt = 0;
	return ubi_trimffs_plan(img, len, WS, ES, NB, isbad, t, emit, t, s);
}

int main(void)
{
	struct t t; struct ubi_trimffs_stats s; uint8_t img[256];
	int i;

	/* all-ff pages skipped, others written, physical = logical on clean flash */
	memset(&t, 0, sizeof(t)); t.fail_at = -1;
	memset(img, 0xff, sizeof(img));
	memset(img + 0, 0x11, 8);			/* page 0 data */
	img[17] = 0x22;					/* page 2: one byte not ff */
	memset(img + 24, 0x33, 8);			/* page 3 */
	CHECK(run(&t, img, 64, &s) == 0);
	CHECK(t.cnt == 8 && s.pages_written == 3 && s.pages_skipped == 5);
	CHECK(t.wr[0] && !t.wr[1] && t.wr[2] && t.wr[3] && !t.wr[4]);
	for (i = 0; i < 8; i++) CHECK(t.phys[i] == (uint64_t)i * WS && t.off[i] == (size_t)i * WS);

	/* a page with 0xff data but a non-ff byte anywhere is not skipped */
	memset(img, 0xff, sizeof(img)); img[7] = 0xfe;
	CHECK(run(&t, img, 8, &s) == 0 && t.wr[0] && s.pages_written == 1);

	/* bad blocks 1 and 2 are skipped forward */
	memset(&t, 0, sizeof(t)); t.fail_at = -1; t.bad[1] = t.bad[2] = 1;
	memset(img, 0x5a, sizeof(img));
	CHECK(run(&t, img, 96, &s) == 0);		/* 3 blocks: 0, 3, 4 */
	CHECK(t.cnt == 12);
	CHECK(t.phys[3] == 24 && t.phys[4] == 3 * ES && t.phys[7] == 3 * ES + 24);
	CHECK(t.phys[8] == 4 * ES && t.phys[11] == 4 * ES + 24);
	CHECK(s.blocks_needed == 3 && s.blocks_good == 6);

	/* exact fit and one byte over (bad blocks reduce headroom) */
	memset(&t, 0, sizeof(t)); t.fail_at = -1; t.bad[0] = t.bad[7] = 1;
	CHECK(run(&t, img, 6 * ES, &s) == 0);
	CHECK(t.phys[0] == ES && t.phys[t.cnt - 1] == 6 * ES + 24);
	t.cnt = 0;
	CHECK(run(&t, img, 6 * ES + 1, &s) == UBI_TRIMFFS_ENOSPC);
	CHECK(t.cnt == 0 && s.blocks_needed == 7 && s.blocks_good == 6);	/* nothing emitted */

	/* trailing partial page: n shorter, ff tail check only covers real bytes */
	memset(&t, 0, sizeof(t)); t.fail_at = -1;
	memset(img, 0xff, sizeof(img));
	CHECK(run(&t, img, 12, &s) == 0 && t.cnt == 2 && t.n[1] == 4 && !t.wr[1]);
	img[11] = 0;
	CHECK(run(&t, img, 12, &s) == 0 && t.wr[1] && t.n[1] == 4);

	/* image whose blocks are entirely ff costs no writes but still needs headroom */
	memset(img, 0xff, sizeof(img));
	CHECK(run(&t, img, 2 * ES, &s) == 0 && s.pages_written == 0 && s.pages_skipped == 8);
	memset(&t, 0, sizeof(t)); t.fail_at = -1; memset(t.bad, 1, 7);
	CHECK(run(&t, img, 2 * ES, &s) == UBI_TRIMFFS_ENOSPC);

	/* callback failure aborts; bad arguments rejected; empty image ok */
	memset(&t, 0, sizeof(t)); t.fail_at = 2;
	CHECK(run(&t, img, 64, &s) == UBI_TRIMFFS_EEMIT && t.cnt == 2);
	t.fail_at = -1;
	CHECK(ubi_trimffs_plan(img, 8, 8, 12, NB, isbad, &t, emit, &t, &s) == UBI_TRIMFFS_EINVAL);
	CHECK(ubi_trimffs_plan(NULL, 8, WS, ES, NB, isbad, &t, emit, &t, &s) == UBI_TRIMFFS_EINVAL);
	CHECK(run(&t, img, 0, &s) == 0 && t.cnt == 0);

	puts("UBI trimffs page plan: PASS");
	return 0;
}
