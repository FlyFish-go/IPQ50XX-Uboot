// SPDX-License-Identifier: GPL-2.0-or-later
#include "evidence.h"
#include <stdlib.h>
#include <string.h>

static uint16_t le16(const uint8_t *p) { return (uint16_t)(p[0] | (unsigned)p[1] << 8); }
static uint32_t le32(const uint8_t *p) { return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
/* The stock boot MBNs are ARM ELF32; bounds-check the ELF program table and
 * each file-backed segment. SBL1 has a NAND preamble before its ELF. */
static int elf_header(const uint8_t *p, size_t avail, uint32_t partition_size, uint32_t base)
{
 uint32_t phoff; unsigned n, entsz; int load=0;
 if (avail < 52 || memcmp(p,"\177ELF\1\1\1",7) ||
     (le16(p+16)!=2 && le16(p+16)!=3) || le16(p+18)!=40 || le32(p+20)!=1 ||
     le16(p+40)!=52 || le16(p+42)!=32) return 0;
 phoff=le32(p+28); n=le16(p+44); entsz=le16(p+42);
 if (!n || n>64 || phoff>avail || n*entsz>avail-phoff || base>partition_size) return 0;
 for (unsigned i=0;i<n;i++) {
  const uint8_t *q=p+phoff+i*entsz; uint32_t off=le32(q+4), size=le32(q+16);
  if (off>partition_size-base || size>partition_size-base-off) return 0;
  if (le32(q)==1 && size && le32(q+20)>=size) load=1;
 }
 return load;
}

int bb_evidence_scan(const struct bb_flash *parts[BB_EVIDENCE_PARTS],
                     bb_evidence_stats_fn stats, struct bb_evidence *out)
{
 static const uint8_t sbl_magic[12]={0xd1,0xdc,0x4b,0x84,0x34,0x10,0xd7,0x73,0x5a,0x43,0x0b,0x7d};
 static const uint32_t offsets[5]={0,0x500000,0x640000,0x100000,0x140000};
 static const uint32_t sizes[5]={0x80000,0x140000,0x140000,0x40000,0x40000};
 const char needle[]="U-Boot 2016";
 uint8_t *buf=malloc(16384); int all=1;
 memset(out,0,sizeof(*out)); out->sampled=1;
 if (!buf || !stats) { free(buf); return -1; }
 for (unsigned i=0;i<5;i++) {
  const struct bb_flash *f=parts[i]; struct bb_evidence_part *p=&out->part[i];
  uint32_t f0=0,c0=0,f1=0,c1=0; size_t carry=0; int banner=0, header=0, readok=1;
  if (!f || f->offset!=offsets[i] || f->size!=sizes[i] || f->page_size!=2048 || f->erase_size!=0x20000 || stats(f->ctx,&f0,&c0)) { all=0; continue; }
  for (uint32_t off=0;off<f->size;off+=2048) {
   uint8_t *page=buf+carry;
   if (bb_flash_read(f,off,page,2048)) { readok=0; break; }
   int nonff=0; for (unsigned j=0;j<2048;j++) if (page[j]!=0xff) { nonff=1; break; }
   p->non_ff+=nonff;
   if (i==0 && off==0 && !memcmp(page,sbl_magic,12)) header=1;
   if (i==0 && off==0x2800) header=header && elf_header(page,2048,f->size,off);
   if ((i==1 || i==2) && off==0) header=elf_header(page,2048,f->size,0);
   if (i==1 || i==2) for (size_t j=0;j+sizeof(needle)-1<=carry+2048;j++)
    if (!memcmp(buf+j,needle,sizeof(needle)-1)) { banner=1; break; }
   carry=sizeof(needle)-2; memmove(buf,buf+carry+2048-carry,carry);
  }
  if (stats(f->ctx,&f1,&c1) || f1<f0 || c1<c0) readok=0;
  else { p->failed=f1-f0; p->corrected=c1-c0; }
  p->read_ok=readok; p->header_ok=i==0?header:(i<=2 ? header && banner : 1);
  if (!readok || p->failed || p->corrected>BB_EVIDENCE_CORRECTED_MAX || !p->header_ok || (i<3 && p->non_ff<64)) all=0;
 }
 free(buf); out->ok=all; return all?0:-1;
}
