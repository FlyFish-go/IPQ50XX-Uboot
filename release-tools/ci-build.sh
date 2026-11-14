#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Compile one device the way a release would. CROSS_COMPILE must be set.
#
#   ci-build.sh h3c A|B|C|D <output-dir>      pinned NAND builds, every ECC and rescue variant
#   ci-build.sh h3c-auto A|B|C|D <output-dir> the release build: NAND detected at boot
#   ci-build.sh defconfig <name> <output-dir> one U-Boot defconfig
#
# RELEASE_LABEL (e.g. v0.2.0) goes into the version string. Build paths are
# mapped to /build/ and the timestamp is the commit time, so a rebuild of the
# same commit gives the same bytes and no build machine path ends up in a binary.
set -euo pipefail

[[ $# == 3 ]] || { sed -n 3,11p "$0" >&2; exit 2; }
kind=$1 name=$2 out=$(realpath -m -- "$3")
src=$(cd -- "$(dirname -- "$0")/.." && pwd)
candidates=$src/release-metadata/uboot-v0.1.0/CANDIDATES.json
mkdir -p "$out"

label=${RELEASE_LABEL:-}
[[ -z $label || $label =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?$ ]] || {
  echo "RELEASE_LABEL must look like v0.2.0 or v0.2.0-rc1" >&2; exit 2; }
export KCFLAGS="${KCFLAGS:+$KCFLAGS }-ffile-prefix-map=$src/=/build/"
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(git -C "$src" show -s --format=%ct HEAD)}
export TZ=UTC LC_ALL=C

# No build machine path may reach a published file.
check_paths() {
  local f
  for f in "$@"; do
    if grep -aqF -- "$src/" "$f"; then
      echo "$f contains the build path $src/" >&2; exit 1
    fi
  done
}

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
      H3C_RELEASE_LABEL=$label \
        "$src/build-release.sh" "$name" "$out/$name-ecc$ecc-r$rescue"
    done
  done
  ;;
h3c-auto)
  # One U-Boot per board for every catalog NAND: h3c-hw-<x>.mbn for the
  # APPSBL partitions and h3c-hw-<x>-ram-rescue.elf, loaded from an older
  # rescue page's web terminal (bootelf) to install the .mbn.
  [[ $name =~ ^[ABCD]$ ]] || { echo "h3c-auto takes A, B, C or D" >&2; exit 2; }
  b=${name,,}
  for rescue in 0 1; do
    echo "== $name auto rescue=$rescue"
    H3C_NAND_AUTO=1 H3C_RAM_RESCUE=$rescue H3C_RELEASE_LABEL=$label \
      "$src/build-release.sh" "$name" "$out/$name-auto-r$rescue"
  done
  mkdir -p "$out/dist"
  cp -- "$out/$name-auto-r0/appsbl.mbn" "$out/dist/h3c-hw-$b.mbn"
  cp -- "$out/$name-auto-r1/h3c-hw-$b-ram-rescue.strip.elf" "$out/dist/h3c-hw-$b-ram-rescue.elf"
  check_paths "$out/dist/h3c-hw-$b.mbn" "$out/dist/h3c-hw-$b-ram-rescue.elf"
  ;;
defconfig)
  export ARCH=arm
  args=(HOST_LOADLIBES=-l:libbsd.so.0)
  make "${args[@]}" -C "$src/u-boot-2016" O="$out/$name" "${name}_defconfig"
  if [[ -n $label ]]; then
    # "" -> "-v0.2.0": the banner reads 2016.01-v0.2.0-<commit>.
    sed -i "s/^CONFIG_LOCALVERSION=\"\(.*\)\"\$/CONFIG_LOCALVERSION=\"\1-$label\"/" "$out/$name/.config"
    make "${args[@]}" -C "$src/u-boot-2016" O="$out/$name" olddefconfig
    grep -q "^CONFIG_LOCALVERSION=\".*-$label\"\$" "$out/$name/.config"
  fi
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

  # RAM trial image for the stock U-Boot (bootm). Not for H3C, which has its own
  # RAM rescue build.
  if ! grep -q '^CONFIG_H3C_IPQ5018_COMMON=y' "$out/$name/.config"; then
    mkdir -p "$out/$name-ram"
    cp -- "$out/$name/.config" "$out/$name-ram/.config"   # same label as the flash build
    echo CONFIG_RAM_TRIAL_BUILD=y >> "$out/$name-ram/.config"
    make "${args[@]}" -C "$src/u-boot-2016" O="$out/$name-ram" olddefconfig
    make "${args[@]}" -C "$src/u-boot-2016" O="$out/$name-ram" -j1
    python3 -I "$src/release-tools/mkramuimg.py" "$out/$name-ram/u-boot" "$out/dist/$name$sfx-ram.uimg"
    check_paths "$out/dist/$name$sfx-ram.uimg"
  fi
  check_paths "$out/dist/$name$sfx.mbn"
  ;;
*)
  echo "Unknown kind: $kind" >&2; exit 2 ;;
esac
