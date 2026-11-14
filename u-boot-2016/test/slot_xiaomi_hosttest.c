/*
 * Host test for include/slot_xiaomi_core.h: the slot rules of the stock
 * Xiaomi bootmiwifi (CR8806), as a truth table and as an exhaustive
 * comparison with a literal transcription of the stock decision.
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <slot_xiaomi_core.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)

/* success: -1 unset, 0 or 1 */
static struct xiaomi_flags F(unsigned long t0, unsigned long t1, unsigned long ota,
			     unsigned long last, int success)
{
	struct xiaomi_flags f = { t0, t1, ota, last, success >= 0, success >= 0 ? success : 0 };
	return f;
}

/* The stock get_boot_slot() as analysed from the original U-Boot. */
static unsigned int stock(const struct xiaomi_flags *f, int *drop)
{
	unsigned long t0 = f->t0, t1 = f->t1, ota = f->ota, last = f->last;
	*drop = 0;
	if (t0 > 1 || t1 > 1 || ota > 1 || last > 1)
		return 0;
	if (ota) {
		unsigned int slot = 1 - last;
		if (f->success_set && f->success == 0) {
			slot = last;
			*drop = 1;
		}
		return slot;
	}
	{
		int fail_of_last = last ? t1 : t0;
		return fail_of_last ? 1 - last : last;
	}
}

struct row { int no; unsigned long t0, t1, ota, last; int s; unsigned int slot; int drop; };

int main(void)
{
	/* rows of the stock state table, one or more concrete inputs each */
	static const struct row rows[] = {
		{ 0, 2, 0, 0, 0, -1, 0, 0 }, { 0, 0, 5, 0, 1, -1, 0, 0 },
		{ 0, 0, 0, 2, 1, -1, 0, 0 }, { 0, 0, 0, 0, 7, -1, 0, 0 },
		{ 1, 0, 0, 0, 0, -1, 0, 0 }, { 1, 0, 1, 0, 0, 1, 0, 0 },
		{ 2, 1, 0, 0, 0, -1, 1, 0 }, { 2, 1, 0, 0, 0, 1, 1, 0 },
		{ 3, 0, 0, 0, 1, -1, 1, 0 }, { 3, 1, 0, 0, 1, 1, 1, 0 },
		{ 4, 0, 1, 0, 1, -1, 0, 0 },
		{ 5, 0, 0, 1, 0, -1, 1, 0 }, { 5, 0, 0, 1, 1, 1, 0, 0 },
		/* T0/T1 are ignored while an OTA is pending */
		{ 5, 1, 1, 1, 0, -1, 1, 0 }, { 5, 1, 0, 1, 1, -1, 0, 0 },
		{ 6, 0, 0, 1, 0, 0, 0, 1 }, { 6, 0, 0, 1, 1, 0, 1, 1 },
		{ 7, 1, 1, 0, 0, -1, 1, 0 }, { 7, 1, 1, 0, 1, -1, 0, 0 },
	};
	struct xiaomi_flags f;
	struct xiaomi_select r;
	unsigned long t0, t1, o, l;
	int s, drop, i;

	for (i = 0; i < (int)(sizeof(rows) / sizeof(rows[0])); i++) {
		f = F(rows[i].t0, rows[i].t1, rows[i].ota, rows[i].last, rows[i].s);
		r = xiaomi_select_core(&f);
		if (r.slot != rows[i].slot || r.drop_ota != rows[i].drop) {
			fprintf(stderr, "FAIL row #%d case %d\n", rows[i].no, i);
			return 1;
		}
	}

	/* non-numeric text reads as 0 (getenv_ulong): the caller maps it, and
	 * "no flags at all" is a normal boot of slot 0 */
	f = F(0, 0, 0, 0, -1);
	CHECK(xiaomi_select_core(&f).slot == 0);

	/* exhaustive: 0..2 for the four flags, S unset/0/1 */
	for (t0 = 0; t0 < 3; t0++) for (t1 = 0; t1 < 3; t1++)
	for (o = 0; o < 3; o++) for (l = 0; l < 3; l++) for (s = -1; s <= 1; s++) {
		f = F(t0, t1, o, l, s);
		r = xiaomi_select_core(&f);
		CHECK(r.slot == stock(&f, &drop));
		CHECK(r.drop_ota == drop);
		CHECK(r.slot <= 1);
		/* dropping only ever happens in the OTA rollback case */
		CHECK(!r.drop_ota || (o == 1 && s == 0));
	}

	/*
	 * Failure marking (rows #8/#9). Stock marks the booted slot for a bad
	 * image, but always sys1 (slot 0) when UBI cannot attach or the
	 * partition is missing. We deliberately mark the slot that really
	 * failed, so a failing slot 1 is not blamed on slot 0 (a reset loop).
	 */
	f = F(0, 0, 0, 0, -1);
	CHECK(xiaomi_failure_core(&f, 0).mark_slot == 0);
	CHECK(!xiaomi_failure_core(&f, 0).both_failed);
	f = F(0, 0, 0, 1, -1);
	CHECK(xiaomi_failure_core(&f, 1).mark_slot == 1);	/* stock: 0 for UBI errors */
	f = F(0, 1, 0, 0, -1);
	CHECK(xiaomi_failure_core(&f, 0).both_failed);		/* slot 1 already marked */
	f = F(1, 0, 0, 0, -1);
	CHECK(!xiaomi_failure_core(&f, 0).both_failed);		/* only itself */
	CHECK(xiaomi_failure_core(&f, 1).both_failed);
	/* after marking and clearing O, the other slot is chosen (rows #2/#4) */
	f = F(0, 0, 0, 0, -1); f.t0 = 1; f.ota = 0;
	CHECK(xiaomi_select_core(&f).slot == 1);
	f = F(0, 0, 0, 1, -1); f.t1 = 1; f.ota = 0;
	CHECK(xiaomi_select_core(&f).slot == 0);
	/* failed OTA: O=1 booting slot 1-L fails -> T[1-L]=1, O=0 -> back to L */
	f = F(0, 0, 1, 0, -1);
	CHECK(xiaomi_select_core(&f).slot == 1);
	f.t1 = 1; f.ota = 0;
	CHECK(xiaomi_select_core(&f).slot == 0);

	/* row #11: crash record clears a pending OTA, otherwise leaves it */
	CHECK(xiaomi_crash_drops_ota(0x10, 1));
	CHECK(!xiaomi_crash_drops_ota(0x10, 0));
	CHECK(!xiaomi_crash_drops_ota(0, 1));
	CHECK(!xiaomi_crash_drops_ota(0x11, 1));
	f = F(0, 0, 1, 0, -1);
	CHECK(xiaomi_select_core(&f).slot == 1);	/* before */
	f.ota = 0;
	CHECK(xiaomi_select_core(&f).slot == 0);	/* after the drop: old slot */

	puts("SLOT_XIAOMI_HOSTTEST_PASS");
	/*
	 * Web upgrade = pending OTA (xiaomi_pending_ota): from every starting
	 * state with sane flags, the next boot is the new slot; a crash of the
	 * new system (crash rule drops O) goes back to the old slot unless the
	 * old one is marked failed; a load failure (T[new]=1, O=0) goes back too.
	 */
	{
		unsigned long t0, t1, last;
		int s, succ;

		for (t0 = 0; t0 <= 1; t0++)
		for (t1 = 0; t1 <= 1; t1++)
		for (last = 0; last <= 1; last++)
		for (succ = -1; succ <= 1; succ++)
		for (s = 0; s <= 1; s++) {
			struct xiaomi_flags f = F(t0, t1, 0, last, succ), g;
			struct xiaomi_select r;
			unsigned long old_failed;

			xiaomi_pending_ota(&f, s);
			old_failed = s ? f.t0 : f.t1;
			CHECK(f.last == (unsigned long)(1 - s) && f.ota == 1);
			CHECK((s ? f.t1 : f.t0) == 0);
			CHECK(f.success_set && f.success == 1);
			r = xiaomi_select_core(&f);
			CHECK(r.slot == (unsigned int)s && !r.drop_ota);
			/* panic in the new system */
			CHECK(xiaomi_crash_drops_ota(XIAOMI_RESET_REASON_CRASH, f.ota));
			g = f;
			g.ota = 0;
			r = xiaomi_select_core(&g);
			CHECK(r.slot == (old_failed ? (unsigned int)s : (unsigned int)(1 - s)));
			/* the new system did not load: slot_boot_failed marks it */
			g = f;
			if (s)
				g.t1 = 1;
			else
				g.t0 = 1;
			g.ota = 0;
			CHECK(xiaomi_failure_core(&g, s).mark_slot == (unsigned int)s);
			if (!old_failed)
				CHECK(xiaomi_select_core(&g).slot == (unsigned int)(1 - s));
		}
	}
	/*
	 * Selecting is not idempotent: with O=1 and S=0 the first call picks L
	 * and drops O, a second call then follows T[L] to the other slot. This
	 * is why slot_boot_failed() blames the slot slot_prepare_boot() chose.
	 */
	{
		struct xiaomi_flags f = F(1, 0, 1, 0, 0);
		struct xiaomi_select r = xiaomi_select_core(&f);

		CHECK(r.slot == 0 && r.drop_ota);
		f.ota = 0;
		CHECK(xiaomi_select_core(&f).slot == 1);
	}
	/*
	 * Pending OTA lifecycle: web upgrade -> first boot writes R -> a clean
	 * reboot confirms (L = new, O = 0) -> later crashes keep the new slot.
	 * A crash before the confirmation goes back to the old slot.
	 */
	{
		int s;

		for (s = 0; s <= 1; s++) {
			struct xiaomi_flags f = F(0, 0, 0, 1 - s, 1);
			unsigned long r = 1 - s;	/* set by xiaomi_slot ota */

			xiaomi_pending_ota(&f, s);
			/* first boot: not confirmed yet (R is still the old slot) */
			CHECK(!xiaomi_ota_confirmed(&f, r, 0));
			CHECK(xiaomi_select_core(&f).slot == (unsigned int)s);
			r = s;				/* slot_prepare_boot writes R */
			/* crash during the first run: no confirmation, rollback */
			CHECK(!xiaomi_ota_confirmed(&f, r, XIAOMI_RESET_REASON_CRASH));
			/* clean reboot: confirmed */
			CHECK(xiaomi_ota_confirmed(&f, r, 0));
			f.last = s;
			f.ota = 0;
			CHECK(xiaomi_select_core(&f).slot == (unsigned int)s);
			CHECK(!xiaomi_crash_drops_ota(XIAOMI_RESET_REASON_CRASH, f.ota));
			CHECK(!xiaomi_ota_confirmed(&f, r, 0));	/* nothing pending */
		}
		/* never confirm a slot marked failed or an explicit S=0 */
		{
			struct xiaomi_flags f = F(0, 1, 1, 0, 1);
			CHECK(!xiaomi_ota_confirmed(&f, 1, 0));
			f = F(0, 0, 1, 0, 0);
			CHECK(!xiaomi_ota_confirmed(&f, 1, 0));
			f = F(0, 0, 2, 0, 1);
			CHECK(!xiaomi_ota_confirmed(&f, 1, 0));
		}
	}
	return 0;
}
