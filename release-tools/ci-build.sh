#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Compile one device the way a release would. CROSS_COMPILE must be set.
#
#   ci-build.sh h3c A|B|C|D <output-dir>      every ECC and rescue variant
#   ci-build.sh defconfig <name> <output-dir> one U-Boot defconfig
set -euo pipefail

[[ $# == 3 ]] || { sed -n 3,7p "$0" >&2; exit 2; }
kind=$1 name=$2 out=$(realpath -m -- "$3")
src=$(cd -- "$(dirname -- "$0")/.." && pwd)
candidates=$src/release-metadata/uboot-v0.1.0/CANDIDATES.json
mkdir -p "$out"

case $kind in
h3c)
  python3 -I - "$candidates" "$name" <<'PY' |
import json, sys
seen = set()
for c in json.load(open(sys.argv[1]))["candidates"]:
    key = (c["board"], c["load_ecc_bits"])
    if c["board"] == sys.argv[2] and key not in seen:
        seen.add(key)
        print(c["nand_profile_id"], c["source_mask"], c["load_ecc_bits"])
PY
  while read -r profile mask ecc; do
    for rescue in 0 1; do
      echo "== $name ECC$ecc rescue=$rescue"
      H3C_NAND_PROFILE_ID=$profile H3C_NAND_SOURCE_MASK=$mask \
      H3C_NAND_LOAD_ECC_BITS=$ecc H3C_NAND_STORAGE_ECC_BITS=$ecc H3C_RAM_RESCUE=$rescue \
        "$src/build-release.sh" "$name" "$out/$name-ecc$ecc-r$rescue"
    done
  done
  ;;
defconfig)
  export ARCH=arm
  args=(HOST_LOADLIBES=-l:libbsd.so.0)
  make "${args[@]}" -C "$src/u-boot-2016" O="$out/$name" "${name}_defconfig"
  make "${args[@]}" -C "$src/u-boot-2016" O="$out/$name" -j1   # dtb_combined is not parallel-safe

  # Flash image for the APPSBL partition. A board nobody has verified on
  # hardware (CONFIG_BOARD_UNTESTED) carries "-untested" in every artifact name.
  sfx=
  grep -q '^CONFIG_BOARD_UNTESTED=y' "$out/$name/.config" && sfx=-untested
  mkdir -p "$out/dist"
  "${CROSS_COMPILE}strip" "$out/$name/u-boot" -o "$out/$name/u-boot.strip.elf"
  python3 -I - "$src/release-tools" "$out/$name/u-boot.strip.elf" "$out/dist/$name$sfx.mbn" <<'PYEOF'
import pathlib, sys
sys.path.insert(0, sys.argv[1])
import appsbl_packager
appsbl_packager.write_outputs(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]))
PYEOF
  ;;
*)
  echo "Unknown kind: $kind" >&2; exit 2 ;;
esac
