// SPDX-License-Identifier: GPL-2.0-or-later
#include "rules.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_TOKENS 24

/* Split a line in place on spaces. Returns the token count, or -1 if the
 * line has too many tokens. Comments and blank lines give 0. */
static int tokenize(char *line, char **tok)
{
	int n = 0;
	char *hash = strchr(line, '#');

	if (hash)
		*hash = 0;
	for (char *p = strtok(line, " \t\r"); p; p = strtok(NULL, " \t\r")) {
		if (n == MAX_TOKENS)
			return -1;
		tok[n++] = p;
	}
	return n;
}

static int hexval(char c)
{
	if (c >= '0' && c <= '9')
		return c - '0';
	c = tolower((unsigned char)c);
	return c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1;
}

/* art5g@<off>=<hex bytes>, one alternative. */
static int match_art(const struct bb_facts *f, const char *offs, const char *hex, size_t hexlen)
{
	char *end;
	unsigned long off = strtoul(offs, &end, 16);

	if (!f->have_art5g || end == offs || *end != '=' || hexlen % 2 ||
	    off + hexlen / 2 > BB_ART5G_BYTES)
		return 0;
	for (size_t i = 0; i < hexlen; i += 2) {
		int hi = hexval(hex[i]), lo = hexval(hex[i + 1]);

		if (hi < 0 || lo < 0 || f->art5g[off + i / 2] != (hi << 4 | lo))
			return 0;
	}
	return 1;
}

/* Value of a scalar fact as text, or NULL when unknown. */
static const char *fact(const struct bb_facts *f, const char *key, char *tmp, size_t len)
{
	if (!strcmp(key, "route"))
		return f->have_route ? f->route : NULL;
	if (!strcmp(key, "layout"))
		return f->layout[0] ? f->layout : NULL;
	if (!strcmp(key, "sbl1.sha256"))
		return f->sbl1_sha256[0] ? f->sbl1_sha256 : NULL;
	if (!strcmp(key, "machid")) {
		if (!f->have_machid)
			return NULL;
		snprintf(tmp, len, "0x%08x", f->machid);
		return tmp;
	}
	if (!strcmp(key, "nand.id")) {
		if (!f->have_nand_id)
			return NULL;
		snprintf(tmp, len, "%02x:%02x", f->nand_mfr, f->nand_chip);
		return tmp;
	}
	if (!strcmp(key, "nand.model"))
		return f->have_nand_model ? f->nand_model : NULL;
	if (!strcmp(key, "product"))
		return f->env_crc_ok && f->productname[0] ? f->productname : NULL;
	if (!strcmp(key, "item"))
		return f->env_crc_ok && f->item_code[0] ? f->item_code : NULL;
	{
		static const struct { const char *k; size_t off; int geo; } nums[] = {
			{ "nand.mib", offsetof(struct bb_facts, nand_mib), 1 },
			{ "nand.page", offsetof(struct bb_facts, nand_page), 1 },
			{ "nand.erase_kib", offsetof(struct bb_facts, nand_erase_kib), 1 },
			{ "nand.oob", offsetof(struct bb_facts, nand_oob), 1 },
			{ "ecc", offsetof(struct bb_facts, mtd_ecc_strength), 0 },
		};

		for (size_t i = 0; i < sizeof(nums) / sizeof(nums[0]); i++) {
			unsigned v;

			if (strcmp(key, nums[i].k))
				continue;
			if (nums[i].geo && !f->have_nand_geometry)
				return NULL;
			memcpy(&v, (const char *)f + nums[i].off, sizeof(v));
			if (!v)
				return NULL;
			snprintf(tmp, len, "%u", v);
			return tmp;
		}
	}
	return NULL;
}

/* One condition "key=alt1|alt2". Unknown keys never match. */
static int match_cond(const struct bb_facts *f, const char *cond)
{
	const char *eq = strchr(cond, '='), *alts;
	char key[32], tmp[24];
	const char *have;
	size_t klen;

	if (!eq || eq == cond)
		return 0;
	klen = eq - cond;
	alts = eq + 1;
	if (klen > 6 && !strncmp(cond, "art5g@", 6)) {
		for (const char *a = alts; *a;) {
			size_t n = strcspn(a, "|");

			if (match_art(f, cond + 6, a, n))
				return 1;
			a += n + (a[n] == '|');
		}
		return 0;
	}
	if (klen >= sizeof(key))
		return 0;
	memcpy(key, cond, klen);
	key[klen] = 0;
	have = fact(f, key, tmp, sizeof(tmp));
	if (!have)
		return 0;
	for (const char *a = alts; *a;) {
		size_t n = strcspn(a, "|");

		if (n == strlen(have) && !strncasecmp(a, have, n))
			return 1;
		a += n + (a[n] == '|');
	}
	return 0;
}

static int known_key(const char *cond)
{
	static const char *const keys[] = {
		"route=", "machid=", "nand.id=", "nand.model=", "nand.mib=", "nand.page=",
		"nand.erase_kib=", "nand.oob=", "ecc=", "product=", "item=", "art5g@",
		"layout=", "sbl1.sha256=", "ecc_evidence=",
	};

	for (size_t i = 0; i < sizeof(keys) / sizeof(keys[0]); i++)
		if (!strncmp(cond, keys[i], strlen(keys[i])))
			return strchr(cond, '=') != NULL;
	return 0;
}

static const char *kv(char **tok, int n, const char *key)
{
	size_t k = strlen(key);

	for (int i = 2; i < n; i++)
		if (!strncmp(tok[i], key, k) && tok[i][k] == '=')
			return tok[i] + k + 1;
	return NULL;
}

int bb_rules_load(struct bb_rules *r, const char *text, unsigned *bad_line)
{
	char *copy, *line, *save = NULL;
	unsigned no = 0;
	int header = 0;

	memset(r, 0, sizeof(*r));
	r->text = strdup(text);
	copy = strdup(text);
	if (!r->text || !copy)
		goto fail;
	for (line = strtok_r(copy, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
		char *tok[MAX_TOKENS];
		int n = tokenize(line, tok);

		no++;
		if (n == 0)
			continue;
		if (n < 0)
			goto fail;
		if (!header) {
			if (n != 2 || strcmp(tok[0], "bbrules") || strcmp(tok[1], "1"))
				goto fail;
			header = 1;
		} else if (!strcmp(tok[0], "set") && n == 2) {
			snprintf(r->set, sizeof(r->set), "%s", tok[1]);
		} else if ((!strcmp(tok[0], "board") || !strcmp(tok[0], "nand")) && n >= 3) {
			for (int i = 2; i < n; i++)
				if (!known_key(tok[i]))
					goto fail;
		} else if (!strcmp(tok[0], "evidence_catalog") && n == 7) {
            unsigned mfr,chip,ecc,oob,raw; char tail;
            if (strcmp(tok[1],"NX54") || sscanf(tok[2],"id=%2x:%2x%c",&mfr,&chip,&tail)!=2 ||
                sscanf(tok[3],"ecc=%u%c",&ecc,&tail)!=1 || sscanf(tok[4],"oob=%u%c",&oob,&tail)!=1 ||
                sscanf(tok[5],"raw=%u%c",&raw,&tail)!=1 || strcmp(tok[6],"target=NX54") ||
                (ecc!=4 && ecc!=8) || r->n_catalog==128) goto fail;
            unsigned i=r->n_catalog++; r->catalog[i].mfr=mfr; r->catalog[i].chip=chip;
            r->catalog[i].ecc=ecc; r->catalog[i].oob=oob; r->catalog[i].raw_oob=raw;
        } else if (!strcmp(tok[0], "evidence_hold") && n == 2) {
            unsigned mfr,chip; char tail;
            if (sscanf(tok[1],"%2x:%2x%c",&mfr,&chip,&tail)!=2 || r->n_hold==128) goto fail;
            r->hold[r->n_hold].mfr=mfr; r->hold[r->n_hold++].chip=chip;
        } else if (!strcmp(tok[0], "candidate") && n >= 3) {
			struct bb_candidate *c;
			const char *b = kv(tok, n, "board"), *nd = kv(tok, n, "nand"),
				   *e = kv(tok, n, "ecc"), *by = kv(tok, n, "bytes"),
				   *h = kv(tok, n, "sha256"), *fl = kv(tok, n, "file"),
				   *pb = kv(tok, n, "part_bytes"), *ph = kv(tok, n, "part_sha256");

			if (r->ncand == BB_RULES_MAX_CANDIDATES || !b || !nd || !e || !by || !h ||
			    !fl || !pb || !ph || strlen(h) != 64 || strlen(ph) != 64)
				goto fail;
			c = &r->cand[r->ncand++];
			snprintf(c->id, sizeof(c->id), "%s", tok[1]);
			snprintf(c->board, sizeof(c->board), "%s", b);
			snprintf(c->nand, sizeof(c->nand), "%s", nd);
			c->ecc = strtoul(e, NULL, 10);
			c->bytes = strtoul(by, NULL, 10);
			snprintf(c->sha256, sizeof(c->sha256), "%s", h);
			c->part_bytes = strtoul(pb, NULL, 10);
			snprintf(c->part_sha256, sizeof(c->part_sha256), "%s", ph);
			snprintf(c->file, sizeof(c->file), "%s", fl);
		} else {
			goto fail;
		}
	}
	free(copy);
	if (!header || !r->set[0]) {
		bb_rules_free(r);
		if (bad_line)
			*bad_line = 0;
		return -1;
	}
	return 0;
fail:
	free(copy);
	bb_rules_free(r);
	if (bad_line)
		*bad_line = no;
	return -1;
}

void bb_rules_free(struct bb_rules *r)
{
	free(r->text);
	r->text = NULL;
	r->ncand = 0;
}

/* Collect the distinct names of all matching `kind` rules. */
static unsigned match_kind(const struct bb_rules *r, const struct bb_facts *f, const char *kind,
			   char names[][64], unsigned max)
{
	char *copy = strdup(r->text), *line, *save = NULL;
	unsigned found = 0;

	if (!copy)
		return 0;
	for (line = strtok_r(copy, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
		char *tok[MAX_TOKENS];
		int n = tokenize(line, tok), ok = 1, dup = 0;

		if (n < 3 || strcmp(tok[0], kind))
			continue;
		for (int i = 2; i < n && ok; i++)
			if (strncmp(tok[i], "ecc_evidence=", 13)) ok = match_cond(f, tok[i]);
		if (!ok)
			continue;
		for (unsigned i = 0; i < found; i++)
			dup |= !strcmp(names[i], tok[1]);
		if (!dup && found < max)
			snprintf(names[found++], 64, "%s", tok[1]);
	}
	free(copy);
	return found;
}

static void list(char *out, size_t len, const char *what, char names[][64], unsigned n)
{
	size_t used = snprintf(out, len, "%s:", what);

	for (unsigned i = 0; i < n && used < len; i++)
		used += snprintf(out + used, len - used, " %s", names[i]);
}

/* The flag is metadata on the already-matched NX54 board line. */
static int evidence_enabled(const struct bb_rules *r, const struct bb_facts *f)
{
 char *copy=strdup(r->text), *line, *save=NULL; int found=0;
 if (!copy) return 0;
 for (line=strtok_r(copy,"\n",&save);line;line=strtok_r(NULL,"\n",&save)) {
  char *tok[MAX_TOKENS]; int n=tokenize(line,tok), ok=1, flag=0;
  if (n<3 || strcmp(tok[0],"board") || strcmp(tok[1],"NX54")) continue;
  for(int i=2;i<n;i++) {
   if (!strcmp(tok[i],"ecc_evidence=1")) flag=1;
   else if (!strncmp(tok[i],"ecc_evidence=",13)) ok=0;
   else if (!match_cond(f,tok[i])) ok=0;
  }
  if(ok && flag) found++;
 }
 free(copy); return found==1;
}

void bb_rules_decide(const struct bb_rules *r, const struct bb_facts *f, struct bb_decision *d)
{
 char names[8][64]; unsigned n, hits=0;
 memset(d,0,sizeof(*d));
 n=match_kind(r,f,"board",names,8); list(d->detail,sizeof(d->detail),"board",names,n);
 if(n!=1) { d->code=n?BB_DEC_AMBIGUOUS_BOARD:BB_DEC_NO_BOARD; return; }
 snprintf(d->board,sizeof(d->board),"%s",names[0]);
 n=match_kind(r,f,"nand",names,8); list(d->detail,sizeof(d->detail),"nand",names,n);
 if(n>1) { d->code=BB_DEC_AMBIGUOUS_NAND; return; }
 if(n==1) snprintf(d->nand,sizeof(d->nand),"%s",names[0]);
 for(unsigned i=0;i<r->ncand;i++) {
  const struct bb_candidate *c=&r->cand[i];
  if(n && !strcmp(c->board,d->board) && !strcmp(c->nand,d->nand) && c->ecc==f->mtd_ecc_strength) { hits++; d->cand=c; }
 }
 if(hits==1) { d->code=BB_DEC_OK; snprintf(d->detail,sizeof(d->detail),"board %s nand %s ecc %u: 1 candidate(s)",d->board,d->nand,f->mtd_ecc_strength); return; }
 if(hits>1) { d->cand=NULL; d->code=BB_DEC_AMBIGUOUS_CANDIDATE; return; }
 d->cand=NULL; d->code=n?BB_DEC_NO_CANDIDATE:BB_DEC_NO_NAND;
 if(strcmp(d->board,"NX54") || !evidence_enabled(r,f) || !f->have_nand_id ||
    !f->have_nand_geometry || f->nand_page!=2048 || f->nand_mib!=128 || f->nand_erase_kib!=128 ||
    (f->mtd_ecc_strength!=4 && f->mtd_ecc_strength!=8)) return;
 for(unsigned i=0;i<r->n_hold;i++)
  if(r->hold[i].mfr==f->nand_mfr && r->hold[i].chip==f->nand_chip) return;
 unsigned matches=0;
 for(unsigned i=0;i<r->n_catalog;i++) {
  if(r->catalog[i].mfr==f->nand_mfr && r->catalog[i].chip==f->nand_chip &&
     r->catalog[i].ecc==f->mtd_ecc_strength && r->catalog[i].oob==f->mtd_oob &&
     r->catalog[i].raw_oob==f->nand_oob) { matches++; d->evidence_oob=r->catalog[i].oob; }
 }
 if(matches!=1) return;
 /* Reuse the one NX54 auto MBN, never choose an arbitrary profile image. */
 for(unsigned i=0;i<r->ncand;i++) if(!strcmp(r->cand[i].board,"NX54")) { hits++; d->cand=&r->cand[i]; }
 if(hits!=1) { d->cand=NULL; return; }
 d->needs_evidence=1;
 if(!f->evidence.sampled || !f->evidence.ok) { d->cand=NULL; return; }
 d->experimental=1; d->code=BB_DEC_OK;
 snprintf(d->detail,sizeof(d->detail),"experimental ECC evidence; corrected limit %u per partition", BB_EVIDENCE_CORRECTED_MAX);
}

int bb_rules_recheck(const struct bb_facts *first, const struct bb_decision *a,
                     const struct bb_facts *second, const struct bb_decision *b)
{
 if (!first || !second || !a || !b || a->code!=BB_DEC_OK || b->code!=BB_DEC_OK)
  return 0;
 if (a->experimental != b->experimental) return 0;
 if (!a->experimental) return 1;
 return first->evidence.ok && second->evidence.ok && first->nand_mfr==second->nand_mfr &&
  first->nand_chip==second->nand_chip && first->mtd_ecc_strength==second->mtd_ecc_strength &&
  first->mtd_oob==second->mtd_oob && first->nand_oob==second->nand_oob;
}

const char *bb_decide_str(enum bb_decide c)
{
	switch (c) {
	case BB_DEC_OK: return "ok";
	case BB_DEC_NO_BOARD: return "no_board";
	case BB_DEC_AMBIGUOUS_BOARD: return "ambiguous_board";
	case BB_DEC_NO_NAND: return "no_nand";
	case BB_DEC_AMBIGUOUS_NAND: return "ambiguous_nand";
	case BB_DEC_NO_CANDIDATE: return "no_candidate";
	case BB_DEC_AMBIGUOUS_CANDIDATE: return "ambiguous_candidate";
	}
	return "unknown";
}

const char *bb_decide_text(enum bb_decide c)
{
	switch (c) {
	case BB_DEC_OK: return "已找到唯一匹配的 U-Boot";
	case BB_DEC_NO_BOARD: return "无法识别主板类型";
	case BB_DEC_AMBIGUOUS_BOARD: return "主板类型判断有冲突";
	case BB_DEC_NO_NAND: return "无法识别闪存型号";
	case BB_DEC_AMBIGUOUS_NAND: return "闪存型号判断有冲突";
	case BB_DEC_NO_CANDIDATE: return "这种主板和闪存的组合没有可用的 U-Boot";
	case BB_DEC_AMBIGUOUS_CANDIDATE: return "有多个 U-Boot 同时匹配";
	}
	return "未知错误";
}
