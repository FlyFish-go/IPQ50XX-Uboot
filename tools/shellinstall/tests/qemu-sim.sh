#!/bin/bash
# End-to-end test of the system installer under qemu-user, against a stock
# firmware rootfs and a simulated NAND built from a real unit's dump.
# Nothing touches a device. Private inputs come from the environment:
#   ROOTFS        extracted stock rootfs (squashfs-root) of the model
#   ROOTFS_WGET   optional: a stock rootfs without curl (busybox wget only),
#                 to test the wget download path and an older busybox/uhttpd
#   DUMP          directory of partition dumps named mtd<N>-<name>.a.bin
#   UBOOT         our U-Boot .mbn for the model
#   MODEL         /proc/device-tree/model string of the unit
#   ARM_CC        static ARM musl compiler
# The stub, uhttpd and the upload CGI run chrooted into a copy of the stock
# rootfs (user + mount namespace, no root needed), so /bin/sh is the OEM
# busybox. Needs binfmt_misc qemu-arm with flags F (works inside a chroot),
# unprivileged user namespaces, and python3, curl, unzip on the host.
set -euo pipefail
echo "qemu-sim: start"
: "${ROOTFS:?}" "${DUMP:?}" "${UBOOT:?}" "${MODEL:?}" "${ARM_CC:?}"
HERE=$(cd "$(dirname "$0")/.." && pwd)
W=$(realpath "${WORK:-$(mktemp -d)}")
PORT=${PORT:-18088}
PORT2=$((PORT + 1))
PASS=0
ok() { echo "PASS $*"; PASS=$((PASS + 1)); }
die() { echo "FAIL $*"; exit 1; }
killpids() { for f in "$@"; do [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true; rm -f "$f"; done; }
cleanup() { killpids "$W"/run/*.pid "$W"/*.pid; }
trap cleanup EXIT

grep -q '^flags:.*F' /proc/sys/fs/binfmt_misc/qemu-arm || die "binfmt qemu-arm needs flag F for chroot"
for p in $PORT $PORT2; do ss -ltn | grep -q "127.0.0.1:$p \|\*:$p \|0.0.0.0:$p " && die "port $p already in use (stale run?)"; done
make -C "$HERE" -s ARM_CC="$ARM_CC"
python3 "$HERE/mkpkg.py" --bin "$HERE/out/arm/ipqi" --version test \
	--entry "uboot/cmcc-mr3000d-ci.mbn=$UBOOT" \
	--url "http://127.0.0.1:9/dead.bin" --url "http://127.0.0.1:$PORT2/ipqi.bin" --out "$W/pkg"
PKG=$W/pkg/ipqi-test.bin
chmod +x "$PKG"
cp "$PKG" "$W/bad.bin"; printf 'x' | dd of="$W/bad.bin" bs=1 seek=100 conv=notrunc 2>/dev/null

# ---- chroot into a copy of a stock rootfs; $W has the same path inside.
mkroot() { # src dst
	rm -rf "$2"; cp -a "$1" "$2"
	rm -f "$2/tmp" "$2/dev" "$2/proc" 2>/dev/null || true
	mkdir -p "$2$W" "$2/dev" "$2/proc" "$2/tmp"
}
inroot() { # root cmd...
	unshare -rm --propagation private sh -c '
		r=$1; w=$2; shift 2
		mount --bind "$w" "$r$w" && mount --rbind /dev "$r/dev" && mount --rbind /proc "$r/proc" &&
		exec chroot "$r" /bin/busybox env PATH=/usr/sbin:/usr/bin:/sbin:/bin "$@"' sh "$1" "$W" "${@:2}"
}
is_arm() { [ "$(od -An -tx1 -j18 -N2 "$1" | tr -d ' ')" = 2800 ]; }
R1=$W/root1
mkroot "$ROOTFS" "$R1"

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

run_stub() { # root [VAR=value...]
	local r=$1; shift
	inroot "$r" IPQI_SIM="$SIM" IPQI_DIR="$W/run" IPQI_PORT=$PORT "$@" /bin/sh "$W/pkg/stub.sh"
}
wait_page() { for _ in $(seq 30); do curl -fs "http://127.0.0.1:$PORT/" | grep -q 上传安装包 && return 0; sleep 1; done; return 1; }
wait_api() {
	for _ in $(seq 60); do curl -fs "http://127.0.0.1:$PORT/api/state" >"$W/state.json" 2>/dev/null && grep -q '"checks"' "$W/state.json" && return 0; sleep 1; done
	return 1
}
jget() { python3 -c "import json,sys;d=json.load(open('$W/state.json'));print(eval(sys.argv[1]))" "$1"; }
post() { curl -fs -X POST -H 'X-IPQI: 1' "http://127.0.0.1:$PORT/api/$1" >"$W/state.json"; }
stop() { killpids "$W"/run/*.pid; sleep 2; }
upload() { curl -fs --data-binary @"$1" "http://127.0.0.1:$PORT/cgi-bin/up"; }
get_backup() {
	post backup; [ "$(jget 'd["backup"]["ready"]')" = True ] || die "backup not ready: $(jget 'd["result"]')"
	curl -fs "http://127.0.0.1:$PORT/backup.zip" -o "$W/backup.zip"
	curl -fs "http://127.0.0.1:$PORT/api/state" >"$W/state.json"
}
serve_sim() { # installer straight on the sim, without the stub
	rm -rf "$W/run5"
	IPQI_SIM="$SIM" "$PKG" serve -p "$PORT" -d "$W/run5" >"$W/serve.log" 2>&1 &
	echo $! > "$W/serve.pid"
	wait_api || die "installer did not start"
}
serve_stop() { post quit || true; killpids "$W/serve.pid"; sleep 1; }
# NAND == base, except the APPSBL copies: <0:APPSBL> <0:APPSBL_1>, each new|old.
nandis() { # base a b
	python3 - "$SIM" "$UBOOT" "$@" <<'PY'
import sys
s, ub, base, a, b = sys.argv[1:]
nand = open(s + '/nand.bin', 'rb').read(); want = bytearray(open(base, 'rb').read()); u = open(ub, 'rb').read()
for l in open(s + '/parts.txt'):
    n, o, z = l.split()[:3]; o, z = int(o, 16), int(z, 16)
    if {'0:APPSBL': a, '0:APPSBL_1': b}.get(n) == 'new':
        want[o:o + z] = u + b'\xff' * (z - len(u))
assert nand == bytes(want), 'NAND differs from expected'
PY
}
# write.log == every erase block of each named partition in turn, ascending;
# "<name>!" = one failed erase at block 0.
order() {
	python3 - "$SIM" "$@" <<'PY'
import sys, os
s, *want = sys.argv[1:]
parts = {l.split()[0]: (int(l.split()[2], 16), int(l.split()[3], 16)) for l in open(s + '/parts.txt')}
p = s + '/write.log'
log = [l.split() for l in open(p)] if os.path.exists(p) else []
exp = []
for w in want:
    if w.endswith('!'):
        exp.append([w[:-1], '0x0', 'fail'])
    else:
        z, e = parts[w]; exp += [[w, hex(o)] for o in range(0, z, e)]
assert log == exp, (len(log), len(exp), log[:3], exp[:3])
PY
}
set_selector() { # 1 = only BOOTCONFIG1 says 1, 2 = both say 1
	python3 - "$SIM" "$1" <<'PY'
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
}

# ---- 1. Command size and stub syntax, in the stock rootfs
is_arm "$R1/bin/busybox" && [ "$(readlink "$R1/bin/sh")" = busybox ] && ok "chroot /bin/sh is the OEM ARM busybox" || die "chroot /bin/sh is the OEM ARM busybox"
[ "$(wc -c < "$W/pkg/command.txt")" -lt 4096 ] && ok "command $(wc -c < "$W/pkg/command.txt") bytes" || die "command too long"
inroot "$R1" /bin/sh -n "$W/pkg/stub.sh" && ok "stub parses in OEM busybox sh" || die "stub parses in OEM busybox sh"
inroot "$R1" /bin/sh -c "base64 -d | gunzip | head -c 9" \
	< <(sed "s/^echo '//;s/' | base64.*//" "$W/pkg/command.txt") | grep -q '^#!/bin/sh' && ok "one-liner decodes in OEM busybox" || die "one-liner decodes in OEM busybox"

# ---- 2. Upload path (no download), CGI under the OEM busybox
run_stub "$R1" IPQI_NO_FETCH=1 | tee "$W/stub-upload.log"
wait_page || die "no upload page"
ok "upload page served by OEM uhttpd"
upload "$W/bad.bin" | grep -q 校验不对 && ok "tampered package rejected (OEM sh CGI)" || die "tampered package rejected (OEM sh CGI)"
upload /etc/hostname | grep -q 大小不对 && ok "wrong-size upload rejected (OEM sh CGI)" || die "wrong-size upload rejected (OEM sh CGI)"
[ "$(upload "$PKG")" = ok ] && ok "package uploaded" || die "package uploaded"
wait_api || die "installer did not take over the port"
ok "installer took over port $PORT"
[ "$(jget 'd["ready"]')" = True ] || { cat "$W/state.json"; die "checks not all passed"; }
ok "all checks pass: $(jget 'd["model"]["title"]')"
jget 'd["checks"][6]["detail"]' | grep -q 偏移较低 && ok "selector 0 detected (lower copy active)" || die "selector 0 detected (lower copy active)"
post install; [ "$(jget 'd["result"]["code"]')" = no_backup ] && ok "install refused before backup download" || die "install refused before backup download"
curl -fs -X POST "http://127.0.0.1:$PORT/api/backup" -o /dev/null && die "POST without X-IPQI accepted" || ok "POST without header refused"
get_backup
[ "$(sha256sum < "$W/backup.zip" | cut -d' ' -f1)" = "$(jget 'd["backup"]["sha256"]')" ] && ok "backup zip sha256 matches" || die "backup zip sha256 matches"
[ "$(jget 'd["backup"]["downloaded"]')" = True ] && ok "backup marked downloaded" || die "backup marked downloaded"
rm -rf "$W/bk"; mkdir "$W/bk"; (cd "$W/bk" && unzip -q ../backup.zip)
for f in "$DUMP"/mtd*-0_ART.a.bin "$DUMP"/mtd*-0_APPSBL.a.bin "$DUMP"/mtd*-0_SBL1.a.bin; do
	n=$(basename "$f" .a.bin); n=${n#mtd*-}
	cmp -s "$f" "$W"/bk/*_"$n".bin && ok "backup $n == dump" || die "backup $n differs"
done
[ -e "$SIM/write.log" ] && die "something was erased before install"
post install; [ "$(jget 'd["result"]["code"]')" = ok ] || die "install: $(jget 'd["result"]')"
ok "install: $(jget 'd["result"]["message"]')"
nandis "$W/nand.orig" new new && ok "both APPSBL == U-Boot + 0xff, every other byte unchanged" || die "both APPSBL == U-Boot + 0xff, every other byte unchanged"
order 0:APPSBL_1 0:APPSBL && ok "write order: spare APPSBL_1 fully, then active APPSBL" || die "write order: spare APPSBL_1 fully, then active APPSBL"
post install; jget 'd["result"]["message"]' | grep -q 没有写入 && ok "second install is a no-op" || die "second install is a no-op"
order 0:APPSBL_1 0:APPSBL && ok "no-op install erased nothing" || die "no-op install erased nothing"
post quit; sleep 2; curl -fs "http://127.0.0.1:$PORT/api/state" >/dev/null 2>&1 && die "still running after quit" || ok "quit stops the installer"
stop

# ---- 3. Download path with the OEM curl, first URL dead
srv_start() { # file to serve as ipqi.bin
	rm -rf "$W/srv"; mkdir "$W/srv"; cp "$1" "$W/srv/ipqi.bin"
	python3 -m http.server "$PORT2" --bind 127.0.0.1 --directory "$W/srv" >/dev/null 2>&1 &
	echo $! > "$W/srv.pid"
	for _ in $(seq 10); do curl -fs "http://127.0.0.1:$PORT2/ipqi.bin" | cmp -s - "$1" && return 0; sleep 1; done
	die "test server on $PORT2 does not serve $1"
}
cp "$W/nand.orig" "$SIM/nand.bin"; rm -f "$SIM/write.log"
srv_start "$PKG"
rm -rf "$W/run"
run_stub "$R1" | tee "$W/stub-fetch.log"
grep -q 安装包已就绪 "$W/stub-fetch.log" && ok "stub downloaded the package with OEM curl (dead mirror skipped)" || die "stub downloaded the package with OEM curl (dead mirror skipped)"
wait_api && [ "$(jget 'd["ready"]')" = True ] && ok "installer up after download" || die "installer up after download"
post quit; stop
killpids "$W/srv.pid"

# ---- 3b. A model without curl: busybox wget download, and upload under its uhttpd
if [ -n "${ROOTFS_WGET:-}" ]; then
	R2=$W/root2
	mkroot "$ROOTFS_WGET" "$R2"
	[ ! -e "$R2/usr/bin/curl" ] && [ "$(readlink "$R2/usr/bin/wget")" = ../../bin/busybox ] &&
		is_arm "$R2/bin/busybox" && ok "second rootfs: no curl, wget is OEM busybox" || die "second rootfs: no curl, wget is OEM busybox"
	rm -rf "$W/run"
	run_stub "$R2" IPQI_NO_FETCH=1 | tee "$W/stub-upload2.log"
	wait_page || die "no upload page (second rootfs)"
	upload "$W/bad.bin" | grep -q 校验不对 && ok "second rootfs: tampered package rejected" || die "second rootfs: tampered package rejected"
	[ "$(upload "$PKG")" = ok ] && wait_api && [ "$(jget 'd["ready"]')" = True ] && ok "second rootfs: upload, installer took over" || die "second rootfs: upload, installer took over"
	post quit; stop
	srv_start "$PKG"
	rm -rf "$W/run"
	run_stub "$R2" | tee "$W/stub-fetch2.log"
	grep -q 安装包已就绪 "$W/stub-fetch2.log" && ok "stub downloaded the package with busybox wget (dead mirror skipped)" || die "stub downloaded the package with busybox wget (dead mirror skipped)"
	cmp -s "$W/run/pkg" "$PKG" && ok "wget copy is byte-identical" || die "wget copy is byte-identical"
	wait_api && [ "$(jget 'd["ready"]')" = True ] && ok "installer up after wget download" || die "installer up after wget download"
	post quit; stop
	killpids "$W/srv.pid"
	# Server that answers with the wrong file: must not start it.
	srv_start "$W/bad.bin"
	rm -rf "$W/run"
	run_stub "$R2" | tee "$W/stub-fetch3.log"
	grep -q 改用上传 "$W/stub-fetch3.log" && [ ! -e "$W/run/pkg" ] && wait_page && ok "bad download refused, fell back to upload page" || die "bad download refused, fell back to upload page"
	stop; killpids "$W/srv.pid"
else
	echo "SKIP 3b: ROOTFS_WGET not set"
fi

# ---- 4. Refusals, via `ipqi check` on altered units
check() { IPQI_SIM="$SIM" "$PKG" check >"$W/state.json" || true; }
expect_fail() { # label substring
	check
	python3 - "$W/state.json" "$1" "$2" <<'PY' && ok "refused: $1 -> $2" || die "refused: $1 -> $2"
import json, sys
d = json.load(open(sys.argv[1])); lab, sub = sys.argv[2:]
assert not d['ready']
c = [c for c in d['checks'] if c['label'] == lab][0]
assert not c['ok'] and sub in c['detail'], c
PY
}
reset() { mksim "$SIM" >/dev/null; }
reset
check; [ "$(jget 'd["ready"]')" = True ] && ok "check passes on clean unit" || die "check passes on clean unit"
echo 1 > "$SIM/fs/sys/devices/system/qfprom/qfprom0/authenticate"; expect_fail 安全启动 已开启; reset
rm "$SIM/fs/sys/devices/system/qfprom/qfprom0/authenticate"; expect_fail 安全启动 读不到; reset
printf 'Qualcomm IPQ5018/AP-MP03.1' > "$SIM/fs/proc/device-tree/model"; expect_fail 机型 不认识; reset
sed -i 's/CMIOT-SR/OTHER/' "$SIM/fs/etc/openwrt_release"; expect_fail 机型 不认识; reset
sed -i '/^0:APPSBL_1 /s/ 0$/ 1/' "$SIM/parts.txt"; expect_fail "U-Boot 分区可写" 只读; reset
sed -i '/^0:ART /s/0x100000/0x80000/' "$SIM/parts.txt"; expect_fail 分区表 0:ART; reset
off=$(awk '$1=="0:APPSBL_1"{print $2}' "$SIM/parts.txt"); echo $((off + 0x40000)) > "$SIM/bad.txt"
expect_fail "U-Boot 分区没有坏块" 坏块; rm "$SIM/bad.txt"
set_selector 1; expect_fail 启动选择记录 说法不一; reset
[ -e "$SIM/write.log" ] && die "check erased something"
ok "check never erases"

# ---- 5. Write order and failures during install
# 5a. Spare copy fails: the active copy must not be touched.
reset
serve_sim; get_backup
echo 0:APPSBL_1 > "$SIM/fail.txt"
post install; [ "$(jget 'd["result"]["code"]')" = write_first ] && ok "spare copy fails -> write_first" || die "spare copy fails -> write_first"
order 0:APPSBL_1! && nandis "$W/nand.orig" old old && ok "after write_first: active APPSBL never erased, NAND unchanged" || die "after write_first: active APPSBL never erased, NAND unchanged"
# 5b. Active copy fails after the spare is done: spare is new, active intact.
rm -f "$SIM/write.log"; echo 0:APPSBL > "$SIM/fail.txt"
post install; [ "$(jget 'd["result"]["code"]')" = write_second ] && ok "active copy fails -> write_second" || die "active copy fails -> write_second"
order 0:APPSBL_1 0:APPSBL! && nandis "$W/nand.orig" old new && ok "after write_second: spare is new U-Boot, active still old" || die "after write_second: spare is new U-Boot, active still old"
# 5c. Retry once the fault is gone: spare is skipped, only the active one is written.
rm -f "$SIM/write.log" "$SIM/fail.txt"
post install; [ "$(jget 'd["result"]["code"]')" = ok ] && ok "retry after write_second -> ok" || die "retry after write_second -> ok"
order 0:APPSBL && nandis "$W/nand.orig" new new && ok "retry wrote only the active copy, both new now" || die "retry wrote only the active copy, both new now"
serve_stop

# 5d. Higher copy active (both BOOTCONFIG say 1): lower copy is written first.
reset; set_selector 2; cp "$SIM/nand.bin" "$W/nand.sel1"
serve_sim
jget 'd["checks"][6]["detail"]' | grep -q 偏移较高 && ok "selector 1 detected (higher copy active)" || die "selector 1 detected (higher copy active)"
get_backup
post install; [ "$(jget 'd["result"]["code"]')" = ok ] || die "install (selector 1): $(jget 'd["result"]')"
order 0:APPSBL 0:APPSBL_1 && nandis "$W/nand.sel1" new new && ok "write order with selector 1: spare APPSBL fully, then active APPSBL_1" || die "write order with selector 1: spare APPSBL fully, then active APPSBL_1"
serve_stop

echo "qemu-sim: ALL $PASS PASS"
