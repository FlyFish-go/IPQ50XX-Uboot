#!/bin/bash
# End-to-end test of the system installer under qemu-user, against a stock
# firmware rootfs and a simulated NAND built from a real unit's dump.
# Nothing touches a device. Private inputs come from the environment:
#   ROOTFS  extracted stock rootfs (squashfs-root) of the model
#   DUMP    directory of partition dumps named mtd<N>-<name>.a.bin
#   UBOOT   our U-Boot .mbn for the model
#   MODEL   /proc/device-tree/model string of the unit
#   ARM_CC  static ARM musl compiler
# Needs binfmt_misc qemu-arm (flags P) and python3, curl, unzip on the host.
set -euo pipefail
echo "qemu-sim: start"
: "${ROOTFS:?}" "${DUMP:?}" "${UBOOT:?}" "${MODEL:?}" "${ARM_CC:?}"
HERE=$(cd "$(dirname "$0")/.." && pwd)
W=${WORK:-$(mktemp -d)}
PORT=${PORT:-18088}
PORT2=$((PORT + 1))
PASS=0
ok() { echo "PASS $*"; PASS=$((PASS + 1)); }
die() { echo "FAIL $*"; exit 1; }
cleanup() {
	for f in "$W"/run/*.pid "$W"/srv.pid; do [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true; done
	rm -f /tmp/ipqi-conf
}
trap cleanup EXIT

make -C "$HERE" -s ARM_CC="$ARM_CC"
python3 "$HERE/mkpkg.py" --bin "$HERE/out/arm/ipqi" --version test \
	--entry "uboot/cmcc-mr3000d-ci.mbn=$UBOOT" \
	--url "http://127.0.0.1:9/dead.bin" --url "http://127.0.0.1:$PORT2/ipqi.bin" --out "$W/pkg"
PKG=$W/pkg/ipqi-test.bin
cp "$PKG" "$W/bad.bin"; printf 'x' | dd of="$W/bad.bin" bs=1 seek=100 conv=notrunc 2>/dev/null

# Simulated unit: partitions back to back, as in the recon table.
mksim() {
	local s=$1 off=0
	rm -rf "$s"; mkdir -p "$s/fs/proc/device-tree" "$s/fs/etc" "$s/fs/sys/devices/system/qfprom/qfprom0"
	: > "$s/parts.txt"
	for f in $(ls "$DUMP"/mtd*-0_*.a.bin | sort -V); do
		n=$(basename "$f" .a.bin); n=${n#mtd*-}; n=0:${n#0_}; sz=$(stat -c %s "$f")
		echo "$n $(printf 0x%x $off) $(printf 0x%x $sz) 0x20000 0x800 0" >> "$s/parts.txt"
		off=$((off + sz))
	done
	for r in rootfs rootfs_1; do
		echo "$r $(printf 0x%x $off) 0x3a00000 0x20000 0x800 0" >> "$s/parts.txt"; off=$((off + 0x3a00000))
	done
	python3 - "$s" "$DUMP" <<'PY'
import sys, glob, os
s, d = sys.argv[1:]
parts = [l.split() for l in open(s + '/parts.txt')]
size = max(int(p[1], 16) + int(p[2], 16) for p in parts)
nand = bytearray(b'\xff' * size)
for p in parts:
    g = glob.glob(os.path.join(d, 'mtd*-%s.a.bin' % p[0].replace(':', '_')))
    if g:
        b = open(g[0], 'rb').read(); o = int(p[1], 16); nand[o:o + len(b)] = b
open(s + '/nand.bin', 'wb').write(nand)
PY
	printf '%s' "$MODEL" > "$s/fs/proc/device-tree/model"
	cp "$ROOTFS/etc/openwrt_release" "$s/fs/etc/"
	echo 0 > "$s/fs/sys/devices/system/qfprom/qfprom0/authenticate"
}

SIM=$W/sim
mksim "$SIM"
cp "$SIM/nand.bin" "$W/nand.orig"
grep -q '0:APPSBL ' "$SIM/parts.txt" || die "sim has no APPSBL"

# Run a stock binary from ROOTFS through qemu (dynamic musl, OEM busybox).
oem() { env PATH="$ROOTFS/usr/sbin:$ROOTFS/usr/bin:$ROOTFS/sbin:$ROOTFS/bin" QEMU_LD_PREFIX="$ROOTFS" "$@"; }
run_stub() {
	oem IPQI_SIM="$SIM" IPQI_DIR="$W/run" IPQI_PORT=$PORT "$@" "$ROOTFS/bin/busybox" sh "$W/pkg/stub.sh"
}
wait_api() {
	for _ in $(seq 60); do curl -fs "http://127.0.0.1:$PORT/api/state" >"$W/state.json" 2>/dev/null && grep -q '"checks"' "$W/state.json" && return 0; sleep 1; done
	return 1
}
jget() { python3 -c "import json,sys;d=json.load(open('$W/state.json'));print(eval(sys.argv[1]))" "$1"; }
post() { curl -fs -X POST -H 'X-IPQI: 1' "http://127.0.0.1:$PORT/api/$1" >"$W/state.json"; }
stop() {
	for f in "$W"/run/*.pid; do [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true; done
	sleep 2
}

# ---- 1. Command size and stub syntax
[ "$(wc -c < "$W/pkg/command.txt")" -lt 4096 ] && ok "command $(wc -c < "$W/pkg/command.txt") bytes" || die "command too long"
oem "$ROOTFS/bin/busybox" sh -n "$W/pkg/stub.sh" && ok "stub parses in OEM busybox sh"
oem "$ROOTFS/bin/busybox" sh -c "base64 -d < /dev/stdin | gunzip | head -c 9" \
	< <(sed "s/^echo '//;s/' | base64.*//" "$W/pkg/command.txt") | grep -q '^#!/bin/sh' && ok "one-liner decodes in OEM busybox"

# ---- 2. Upload path (no download)
run_stub IPQI_NO_FETCH=1 | tee "$W/stub-upload.log"
for _ in $(seq 30); do curl -fs "http://127.0.0.1:$PORT/" | grep -q 上传安装包 && break; sleep 1; done
ok "upload page served by OEM uhttpd"
curl -fs --data-binary @"$W/bad.bin" "http://127.0.0.1:$PORT/cgi-bin/up" | grep -q 校验不对 && ok "tampered package rejected"
curl -fs --data-binary @/etc/hostname "http://127.0.0.1:$PORT/cgi-bin/up" | grep -q 大小不对 && ok "wrong-size upload rejected"
[ "$(curl -fs --data-binary @"$PKG" "http://127.0.0.1:$PORT/cgi-bin/up")" = ok ] && ok "package uploaded"
wait_api || die "installer did not take over the port"
ok "installer took over port $PORT"
[ "$(jget 'd["ready"]')" = True ] || { cat "$W/state.json"; die "checks not all passed"; }
ok "all checks pass: $(jget 'd["model"]["title"]')"
post install; [ "$(jget 'd["result"]["code"]')" = no_backup ] && ok "install refused before backup download"
curl -fs -X POST "http://127.0.0.1:$PORT/api/backup" -o /dev/null && die "POST without X-IPQI accepted" || ok "POST without header refused"
post backup; [ "$(jget 'd["backup"]["ready"]')" = True ] || die "backup not ready: $(jget 'd["result"]')"
curl -fs "http://127.0.0.1:$PORT/backup.zip" -o "$W/backup.zip"
curl -fs "http://127.0.0.1:$PORT/api/state" >"$W/state.json"
[ "$(sha256sum < "$W/backup.zip" | cut -d' ' -f1)" = "$(jget 'd["backup"]["sha256"]')" ] && ok "backup zip sha256 matches"
[ "$(jget 'd["backup"]["downloaded"]')" = True ] && ok "backup marked downloaded"
rm -rf "$W/bk"; mkdir "$W/bk"; (cd "$W/bk" && unzip -q ../backup.zip)
for f in "$DUMP"/mtd*-0_ART.a.bin "$DUMP"/mtd*-0_APPSBL.a.bin "$DUMP"/mtd*-0_SBL1.a.bin; do
	n=$(basename "$f" .a.bin); n=${n#mtd*-}
	cmp -s "$f" "$W"/bk/*_"$n".bin && ok "backup $n == dump" || die "backup $n differs"
done
post install; [ "$(jget 'd["result"]["code"]')" = ok ] || die "install: $(jget 'd["result"]')"
ok "install: $(jget 'd["result"]["message"]')"
python3 - "$SIM" "$UBOOT" "$W/nand.orig" <<'PY' && ok "both APPSBL == U-Boot + 0xff, every other byte unchanged"
import sys
s, ub, orig = sys.argv[1:]
nand = open(s + '/nand.bin', 'rb').read(); old = open(orig, 'rb').read(); u = open(ub, 'rb').read()
touched = []
for l in open(s + '/parts.txt'):
    n, o, z = l.split()[:3]; o, z = int(o, 16), int(z, 16)
    if n in ('0:APPSBL', '0:APPSBL_1'):
        want = u + b'\xff' * (z - len(u))
        assert nand[o:o + z] == want, n
        touched.append((o, z))
for o, z in touched:
    nand = nand[:o] + old[o:o + z] + nand[o + z:]
assert nand == old, 'bytes outside APPSBL changed'
PY
post install; jget 'd["result"]["message"]' | grep -q 没有写入 && ok "second install is a no-op"
post quit; sleep 2; curl -fs "http://127.0.0.1:$PORT/api/state" >/dev/null 2>&1 && die "still running after quit" || ok "quit stops the installer"
stop

# ---- 3. Download path (curl from the OEM rootfs, first URL dead)
cp "$W/nand.orig" "$SIM/nand.bin"
rm -rf "$W/srv"; mkdir "$W/srv"; cp "$PKG" "$W/srv/ipqi.bin"
(cd "$W/srv" && python3 -m http.server "$PORT2" --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > "$W/srv.pid")
sleep 1
rm -rf "$W/run"
run_stub | tee "$W/stub-fetch.log"
grep -q 安装包已就绪 "$W/stub-fetch.log" && ok "stub downloaded the package (dead mirror skipped)"
wait_api && [ "$(jget 'd["ready"]')" = True ] && ok "installer up after download"
post quit; stop
kill "$(cat "$W/srv.pid")" 2>/dev/null || true; rm -f "$W/srv.pid"

# ---- 4. Refusals, via `ipqi check` on altered units
chmod +x "$PKG"
check() { IPQI_SIM="$SIM" "$PKG" check >"$W/state.json" || true; }
expect_fail() { # label substring
	check
	python3 - "$W/state.json" "$1" "$2" <<'PY' && ok "refused: $1 -> $2"
import json, sys
d = json.load(open(sys.argv[1])); lab, sub = sys.argv[2:]
assert not d['ready']
c = [c for c in d['checks'] if c['label'] == lab][0]
assert not c['ok'] and sub in c['detail'], c
PY
}
reset() { mksim "$SIM" >/dev/null; }
check; [ "$(jget 'd["ready"]')" = True ] && ok "check passes on clean unit"
echo 1 > "$SIM/fs/sys/devices/system/qfprom/qfprom0/authenticate"; expect_fail 安全启动 已开启; reset
rm "$SIM/fs/sys/devices/system/qfprom/qfprom0/authenticate"; expect_fail 安全启动 读不到; reset
printf 'Qualcomm IPQ5018/AP-MP03.1' > "$SIM/fs/proc/device-tree/model"; expect_fail 机型 不认识; reset
sed -i 's/CMIOT-SR/OTHER/' "$SIM/fs/etc/openwrt_release"; expect_fail 机型 不认识; reset
sed -i '/^0:APPSBL_1 /s/ 0$/ 1/' "$SIM/parts.txt"; expect_fail "U-Boot 分区可写" 只读; reset
sed -i '/^0:ART /s/0x100000/0x80000/' "$SIM/parts.txt"; expect_fail 分区表 0:ART; reset
off=$(awk '$1=="0:APPSBL_1"{print $2}' "$SIM/parts.txt"); echo $((off + 0x40000)) > "$SIM/bad.txt"
expect_fail "U-Boot 分区没有坏块" 坏块; rm "$SIM/bad.txt"
# BOOTCONFIG1 says APPSBL selector 1, BOOTCONFIG says 0 -> refuse.
python3 - "$SIM" 1 <<'PY'
import sys, struct
s, which = sys.argv[1], sys.argv[2]
parts = {l.split()[0]: int(l.split()[1], 16) for l in open(s + '/parts.txt')}
n = bytearray(open(s + '/nand.bin', 'rb').read())
names = ['0:BOOTCONFIG1'] if which == '1' else ['0:BOOTCONFIG', '0:BOOTCONFIG1']
for name in names:
    o = parts[name]
    for i in range(16):
        e = o + 12 + i * 20
        if n[e:e + 16].rstrip(b'\0') == b'0:APPSBL':
            n[e + 16:e + 20] = struct.pack('<I', 1)
open(s + '/nand.bin', 'wb').write(n)
PY
expect_fail 启动选择记录 说法不一; reset
# Both say selector 1: allowed, and the lower copy is written first.
python3 - "$SIM" 2 <<'PY'
import sys, struct
s = sys.argv[1]
parts = {l.split()[0]: int(l.split()[1], 16) for l in open(s + '/parts.txt')}
n = bytearray(open(s + '/nand.bin', 'rb').read())
for name in ('0:BOOTCONFIG', '0:BOOTCONFIG1'):
    o = parts[name]
    for i in range(16):
        e = o + 12 + i * 20
        if n[e:e + 16].rstrip(b'\0') == b'0:APPSBL':
            n[e + 16:e + 20] = struct.pack('<I', 1)
open(s + '/nand.bin', 'wb').write(n)
PY
check; [ "$(jget 'd["ready"]')" = True ] && jget 'd["checks"][6]["detail"]' | grep -q 偏移较高 && ok "selector 1 detected (higher copy active)"
reset

echo "qemu-sim: ALL $PASS PASS"
