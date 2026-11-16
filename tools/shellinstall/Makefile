# System installer (stage 2). `make` builds out/arm/ipqi with the static ARM
# musl toolchain; mkpkg.py then appends the U-Boot images.
ARM_CC ?= arm-openwrt-linux-muslgnueabi-gcc
CFLAGS := -Os -static -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror
BB2 := ../bootbridge2/runtime
SRC := src/ipqi_main.c src/ipqi_flash.c src/profile.c src/payload.c \
       $(BB2)/flash.c $(BB2)/flash_mtd.c $(BB2)/bootconfig.c $(BB2)/backup.c $(BB2)/sha256.c
OUT := out

all: $(OUT)/arm/ipqi

$(OUT)/www_index.h: www/index.html
	@mkdir -p $(OUT)
	cd www && xxd -i index.html > ../$@.tmp && sed 's/unsigned char index_html/static const unsigned char www_index_html/;s/unsigned int index_html_len/static const unsigned www_index_html_len/' ../$@.tmp > ../$@ && rm ../$@.tmp

$(OUT)/arm/ipqi: $(SRC) $(wildcard src/*.h $(BB2)/*.h) $(OUT)/www_index.h
	@mkdir -p $(OUT)/arm
	$(ARM_CC) $(CFLAGS) -I$(OUT) -o $@ $(SRC)

clean:
	rm -rf $(OUT)

.PHONY: all clean
