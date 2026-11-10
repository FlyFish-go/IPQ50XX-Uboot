#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <h3c_nand_catalog.h>

typedef uint8_t u8;
int h3c_build_id_check(const u8 *image, size_t size);
const char *h3c_build_id(void);

/* What the run-time selection detected on this fake device. */
static const struct h3c_nand_catalog_profile *detected;
static unsigned int detected_mode;
const struct h3c_nand_catalog_profile *h3c_nand_auto_row(void) { return detected; }
unsigned int h3c_nand_auto_mode(void) { return detected_mode; }

static int check(const char *a, const char *b)
{
	u8 buf[512];

	memset(buf, 0xa5, sizeof(buf));
	strcpy((char *)buf + 40, a);
	if (b)
		strcpy((char *)buf + 240, b);
	return h3c_build_id_check(buf, sizeof(buf));
}

#define ID(board, prof, mask, ecc) \
	"H3C-UBOOT-ID:v1;board=" board ";profile=" prof ";mask=" mask ";ecc=" ecc ";"
#define EFBA "h3c-oem-efba-128m-2k-sp64"

int main(void)
{
	unsigned int i;

	for (i = 0; i < H3C_NAND_CATALOG_PROFILE_COUNT; i++)
		if (!strcmp(h3c_nand_catalog_profiles[i].profile_id, EFBA))
			detected = &h3c_nand_catalog_profiles[i];
	assert(detected);
	detected_mode = 4;
#ifdef CONFIG_H3C_NAND_AUTO_PROFILE
	/* running: auto image on board A, detected efba ECC4 */
	assert(!strcmp(h3c_build_id(), ID("A", "auto", "none", "none")));
	assert(check(ID("A", "auto", "none", "none"), NULL) == 0);
	assert(check(ID("A", EFBA, "0x1", "4"), NULL) == 0);
	assert(check(ID("A", EFBA, "0x1", "8"), NULL) == -EXDEV);
	assert(check(ID("A", EFBA, "0x3", "4"), NULL) == -EXDEV);	/* not one source */
	assert(check(ID("A", EFBA, "0x0", "4"), NULL) == -EXDEV);
	assert(check(ID("A", EFBA, "none", "4"), NULL) == -EXDEV);
	assert(check(ID("A", EFBA, "0x20", "4"), NULL) == -EXDEV);	/* source not in row */
	assert(check(ID("A", "h3c-oem-efbc-128m-2k-sp64", "0x1", "4"), NULL) == -EXDEV);
	assert(check(ID("B", EFBA, "0x1", "4"), NULL) == -EXDEV);
	assert(check(ID("B", "auto", "none", "none"), NULL) == -EXDEV);
	assert(check(ID("A", "auto", "0x1", "4"), NULL) == -EXDEV);	/* malformed auto */
	assert(check(ID("A", "", "none", "none"), NULL) == -EXDEV);	/* legacy unpinned */
	assert(check(ID("A", EFBA, "0x1", "4") "x", NULL) == -EXDEV);	/* trailing text */
	assert(check("H3C-UBOOT-ID:v1;board=A;profile=auto;mask=none;ecc=none", NULL) == -EXDEV);
	assert(check(ID("A", "auto", "none", "none"), ID("A", "auto", "none", "none")) == -EEXIST);
	/* nothing detected: only auto uploads are acceptable */
	detected = NULL; detected_mode = 0;
	assert(check(ID("A", "auto", "none", "none"), NULL) == 0);
	assert(check(ID("A", EFBA, "0x1", "4"), NULL) == -EXDEV);
#else
	/* running: image pinned to efba/0x1/ECC4 on board A */
	assert(!strcmp(h3c_build_id(), ID("A", EFBA, "0x1", "4")));
	assert(check(ID("A", EFBA, "0x1", "4"), NULL) == 0);
	assert(check(ID("A", "auto", "none", "none"), NULL) == 0);
	assert(check(ID("B", "auto", "none", "none"), NULL) == -EXDEV);
	assert(check(ID("A", EFBA, "0x1", "8"), NULL) == -EXDEV);
	assert(check(ID("A", "h3c-oem-efbc-128m-2k-sp64", "0x1", "4"), NULL) == -EXDEV);
	assert(check(ID("A", "", "none", "none"), NULL) == -EXDEV);
	assert(check("no id here", NULL) == -ENOENT);
#endif
	puts("PASS");
	return 0;
}
