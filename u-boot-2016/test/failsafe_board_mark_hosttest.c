// SPDX-License-Identifier: GPL-2.0+
#include <stdio.h>
#include <string.h>
#include "failsafe_board_mark.h"

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); fails++; } } while (0)

static const char P[] = FAILSAFE_BOARD_MARK_PREFIX;
#define PL (sizeof(P) - 1)

static int chk(const void *img, size_t n, const char *own, char *found)
{
	return failsafe_board_mark_check(img, n, P, PL, own, found,
					 FAILSAFE_BOARD_MARK_ID_MAX + 1);
}

/* image = junk + mark(s) + junk; the mark carries its NUL */
static size_t build(unsigned char *buf, const char *const *ids, int k)
{
	size_t n = 0;
	int i;

	memset(buf, 0xa5, 64); n = 64;
	for (i = 0; i < k; i++) {
		size_t l = strlen(ids[i]);
		memcpy(buf + n, P, PL); n += PL;
		memcpy(buf + n, ids[i], l + 1); n += l + 1;
		memset(buf + n, 0x5a, 16); n += 16;
	}
	return n;
}

int main(void)
{
	unsigned char buf[1024];
	char found[FAILSAFE_BOARD_MARK_ID_MAX + 1];
	const char *own = "ipq5018_cmcc_rax3000q";
	const char *same[] = { "ipq5018_cmcc_rax3000q" };
	const char *other[] = { "ipq5018_lingyan_lyw_30m" };
	const char *prefix_of_own[] = { "ipq5018_cmcc_rax3000" };
	const char *longer[] = { "ipq5018_cmcc_rax3000q_v2" };
	const char *two[] = { "ipq5018_cmcc_rax3000q", "ipq5018_cmcc_rax3000q" };
	char longid[80];
	size_t n;

	n = build(buf, same, 1);
	CHECK(chk(buf, n, own, found) == FAILSAFE_BOARD_MARK_OK);
	CHECK(!strcmp(found, own));

	n = build(buf, other, 1);
	CHECK(chk(buf, n, own, found) == FAILSAFE_BOARD_MARK_MISMATCH);
	CHECK(!strcmp(found, other[0]));
	n = build(buf, prefix_of_own, 1);
	CHECK(chk(buf, n, own, found) == FAILSAFE_BOARD_MARK_MISMATCH);
	n = build(buf, longer, 1);
	CHECK(chk(buf, n, own, found) == FAILSAFE_BOARD_MARK_MISMATCH);

	n = build(buf, NULL, 0);
	CHECK(chk(buf, n, own, found) == FAILSAFE_BOARD_MARK_MISSING);
	CHECK(found[0] == '\0');
	CHECK(chk(NULL, 0, own, found) == FAILSAFE_BOARD_MARK_MISSING);
	CHECK(chk(P, PL - 1, own, found) == FAILSAFE_BOARD_MARK_MISSING);

	n = build(buf, two, 2);
	CHECK(chk(buf, n, own, found) == FAILSAFE_BOARD_MARK_MULTIPLE);

	/* mark at the very end without its NUL */
	memcpy(buf, P, PL); memcpy(buf + PL, own, strlen(own));
	CHECK(chk(buf, PL + strlen(own), own, found) == FAILSAFE_BOARD_MARK_BAD);
	/* bad characters, empty id, overlong id */
	memcpy(buf, P, PL); memcpy(buf + PL, "IPQ5018\"x", 10);
	CHECK(chk(buf, PL + 10, own, found) == FAILSAFE_BOARD_MARK_BAD);
	memcpy(buf, P, PL); buf[PL] = 0;
	CHECK(chk(buf, PL + 1, own, found) == FAILSAFE_BOARD_MARK_BAD);
	memset(longid, 'a', sizeof(longid)); longid[FAILSAFE_BOARD_MARK_ID_MAX + 1] = 0;
	memcpy(buf, P, PL); memcpy(buf + PL, longid, FAILSAFE_BOARD_MARK_ID_MAX + 2);
	CHECK(chk(buf, PL + FAILSAFE_BOARD_MARK_ID_MAX + 2, own, found) == FAILSAFE_BOARD_MARK_BAD);
	longid[FAILSAFE_BOARD_MARK_ID_MAX] = 0;	/* exactly ID_MAX chars is fine */
	memcpy(buf, P, PL); memcpy(buf + PL, longid, FAILSAFE_BOARD_MARK_ID_MAX + 1);
	CHECK(chk(buf, PL + FAILSAFE_BOARD_MARK_ID_MAX + 1, longid, found) == FAILSAFE_BOARD_MARK_OK);

	/* this build has no usable id: refuse everything */
	n = build(buf, same, 1);
	CHECK(chk(buf, n, "", found) == FAILSAFE_BOARD_MARK_UNSET);
	CHECK(chk(buf, n, "Bad-Id", found) == FAILSAFE_BOARD_MARK_UNSET);
	CHECK(failsafe_board_mark_check(buf, n, P, PL, own, found, FAILSAFE_BOARD_MARK_ID_MAX) == FAILSAFE_BOARD_MARK_UNSET);

	if (fails) return 1;
	puts("failsafe_board_mark: all checks passed");
	return 0;
}
