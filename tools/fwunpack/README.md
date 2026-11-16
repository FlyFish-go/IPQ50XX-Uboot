# 离线固件拆包

面向指南站的独立工具，放在 `tools/fwunpack/`，避免与 U-Boot 运行时代码和 BootBridge 安装工具耦合。只输出经过严格结构校验的 UBI，不输出独立分区或引导链。

`core.js` 是无依赖的 classic script / CommonJS 模块。`unpack(Uint8Array, {target})` 返回 UBI 字节、格式链、SHA-256、NAND 几何、卷表、内核身份和警告。失败抛出带原因的 Error。`cli.cjs` 读写本地文件，输出文件使用独占创建，避免覆盖已有文件。

```sh
node tools/fwunpack/cli.cjs input.bin output.ubi
node --test tools/fwunpack/tests/core.test.cjs
python3 -I tools/fwunpack/tests/validator.py
python3 site/build.py
```

测试需要 Node 24、Python 3、gcc、mtd-utils `ubinize`（也可用 `UBINIZE` 指定路径）。生产模块和网页不需要这些工具。

`panel.html` 是嵌入现有站点的表单；`app.js` 在 Blob Web Worker 中运行同一个核心，通过 transferable buffer 传入数据。构建复制这两个 JS 文件，机型列表从 `site/devices/*.yaml` 生成，FIT config 名从板级 DTS 读取。使用普通脚本和 Blob Worker，以便完整保存站点后在 `file://` 下离线使用。

## 结构规则

| 规则 | 识别和处理 |
|---|---|
| H3C | 起始 `H3C_`，0xa0 后必须是合法 FIT |
| 锐捷 | `12468ace ce8a4612`，头长度字段为 0x800，之后为 FIT |
| FIT | `d00dfeed`，检查 FDT 结构／边界；校验所有 image 的 crc32 / sha1 / sha256 hash 节点；支持 data、data-offset、data-position；只选唯一系统候选段 |
| HDR1 | `HDR1`、小端段表、`babe` 段头、边界和 JAMCRC；只递归系统段 |
| tar | 校验 tar 头，识别唯一 sysupgrade 目录及 CONTROL / kernel / root；递归 root 容器或为标准 SquashFS 生成 UBI |
| fwtool 尾部 | `FWx0`、大小、类型、全前缀 CRC；移除元数据和签名尾部，签名真实性未验证 |
| ELECOM / CMOC | 产品头后必须为 CMOC；CMOC 依据 payload 长度推出 FIT 位置，校验 payload CRC |
| 裸 UBI | `UBI#`、固定几何、EC/VID CRC、冗余卷表、卷记录与数据 CRC、连续 LEB 和 FIT/SquashFS 魔数 |
| 京东云旧 eMMC FIT | FIT description 的 Flashing emmc 且没有 UBI 段时明确拒绝，未用真实样本验证，不宣称支持 |
| ASUS eMMC | 旧解析器的 uImage + `imag` 魔数只用于给出不支持原因，未用真实样本验证，不宣称支持 |

规则不读 catalog，不按固件哈希或版本识别。输入自带的完整性校验与输出 SHA-256 不构成白名单。改变内容并重算校验的新版本也可拆。

## UBI 与救援端的关系

核心对应 `u-boot-2016/failsafe/modules/firmware_rt3000_b.c::fw_validate_ubi()`，通用路径 `failsafe.c` / `FW_TYPE_UBI` 的要求更宽松。工具使用较严格的一条，并额外限制卷标志、重复属性、段重叠和容器复杂度。

当前救援上传上限为 **80 MiB**，PEB 128 KiB、VID 2048、data 4096、LEB 126976；928 是最大槽 PEB 数，不能当作上传上限。机型容量检查使用 `max(image_pebs, reserved_pebs + 4)`。坏块数与实际分区表只能由设备确认；页面仅报告结构通过，并提示以救援页校验为准。H3C 带 wifi_fw / bt_fw 的原厂镜像还受双系统布局限制。

sysupgrade 生成器固定使用 `-p 131072 -m 2048 -s 2048 -O 2048 -e 0 -Q 0`，三个 dynamic 卷依次为 kernel、rootfs、rootfs_data（预留一个 LEB，autoresize）。它只适用于从这些 UBI 卷启动的 NAND 系统，不适用于独立内核分区、eMMC 或不同几何。

不会解压 SquashFS；显示内核 FIT 的描述、config 和未压缩 DTB compatible。集客修改的超级块显示“无法识别”，不会因此拒绝合法 UBI。

## 私有验证

所有输入路径由环境变量提供，厂商文件、输出 UBI、下载来源和日志只能放在私有输出目录。仓库不包含厂商夹具。先设定 `OUT`、`H3C_OEM_CATALOG`、`NX54_OFFICIAL`、`JIKE_DIR`、`XIAOMI_DIR`、`RUIJIE_DIR`、`RAX3000QY_DIR`、`UBINIZE`：

```sh
python3 -I tools/fwunpack/tests/private.py
python3 -I tools/fwunpack/tests/crosscheck.py
FWUNPACK_E2E_MANIFEST="$OUT/private-manifest.json" node tools/fwunpack/tests/e2e.cjs
```

`private.py` 只在测试中核对 catalog 的包哈希、UBI 哈希、rootfs bytes_used 哈希和 libfdt 提取结果，并调用生产 C 校验器。`private-new-version.cjs` 修改私有 H3C 样本的版本和 rootfs 数据，重算 FIT 自带 hash，证明不需要 catalog 更新。结果表在 `$OUT/results/private.{json,md}`，下载样本置于 `$OUT/samples/<来源>/` 并附 `.source.json` 记录 URL、SHA-256。

浏览器测试需要 Playwright 和 Chromium，可用 `CHROMIUM` 指定可执行文件；合成夹具通过 `FWUNPACK_FIXTURES` 指定目录，在公开测试时生成。e2e 在 `file://`、offline 模式下验证下载与 node CLI 一致、坏文件清除旧下载、拖入、取消与移动端布局，并要求零 HTTP 请求。
