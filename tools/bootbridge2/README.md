# BootBridge v2（开发中）

BootBridge 的重写版本。NX30 家族使用 BB2-R8 直接安装正式 U-Boot v0.2.0；NX54 为测试支持（网页标为测试中）。旧版 `tools/bootbridge/` 仅作历史参考。

网页与安装指南共用 IPQ50XX-Uboot 的 GitHub Pages：`/IPQ50XX-Uboot/bootbridge/`。Actions 只使用仓库内固定的规则/计划资产和网页源码，不读取私有官方包，不发布含厂商文件的基础镜像。公开计划采用 `build_bridge.py --public-plan`，每段字面量有来源记录，原厂压缩块全部 COPY，禁止 XOR 掩码。完整发布输入与更新流程见 [web/release/README.md](web/release/README.md)。NX54 的显示/候选开关为 `site/data/bootbridge.json` 的 `nx54=hidden|testing`。

当前内容：

| 路径 | 内容 |
|---|---|
| `runtime/bootconfig.[ch]` | 解析和改写 QCA 双系统 BOOTCONFIG 记录 |
| `runtime/ubi_check.[ch]` | 只读检查一个 rootfs 槽里是否有可启动的 UBI 系统（`kernel` 静态卷 CRC、`ubi_rootfs` 为 squashfs） |
| `runtime/oem_return.[ch]` | 回原厂：把 rootfs selector 指回桥接没有运行的那个槽 |
| `runtime/flash*.[ch]` | NAND 分区访问；全 0xff 的页不编程 |
| `runtime/bb_oem_return_main.c` | 设备端工具 `bb-oem-return check|commit` |
| `tests/` | 主机测试，含模拟 NAND 和写入失败注入 |

## 回原厂的规则

- 只要求：原厂槽的 UBI 系统完好；两份 BOOTCONFIG 至少一份能解析，且所在块不是坏块。
- 不看 ENV、规则、候选、板型和安装结果。
- selector 0 对应较低偏移的槽，1 对应较高的槽。
- 先写 BOOTCONFIG1，再写 BOOTCONFIG；每份写完都读回比较。两份的 age 都设为原来两份中较大的值加 1。每份其余字节保持各自原样；无法解析的那份用另一份重建。

## 构建与测试

```bash
make test        # 需要 BB_FIXTURES 指向私有的真实分区样本，见 tests/test_oem_return.c
make arm ARM_CC=arm-openwrt-linux-gcc
```

## 当前开发验收

- 规则包使用 BBPK v1：规则文本与 LZMA 候选归档，SHA-256 校验；无签名。
- mp02.1 用 ART 中的 FEM 标志区分 B/D；未知组合拒绝安装。
- WPS/Mesh 使用原厂 gpio-button-hotplug 内核事件；长按 3 秒由独立 bb-keyd 调用 `bb-oem-return commit-reboot`。
- HTTP 备份、安装、返回、重启与独立返回工具共用内核文件锁；锁忙时拒绝操作，进程退出自动释放。
- 安装前完整读回备份 ZIP 并校验大小、SHA-256；写入 APPSBL 前要求有效 BOOTCONFIG 的 APPSBL 选择位明确且一致。
- 两份 APPSBL 均按擦除块读回校验，最后切换系统启动选择位。备用 APPSBL 写入失败时保留当前副本。
- 调试用原始分区与规则包下载接口不随本版保留；设备事实仍可通过诊断下载获取。

主机测试需要外部 `BB_FIXTURES`、`BB_RULES`、`BB_PACK`；`make test` 也覆盖跨进程锁竞争和备份损坏。
网页测试入口为 `web/tests/e2e.js`，逐个校验五种官方固件的浏览器输出（含 NX54）。
设备页面测试为 `tests/e2e_device.js`；仅在明确授权的台架上使用 `--install`，它会实际写入 U-Boot。
实机通过范围以对应私有验收报告为准，不由主机测试数推断。

## NX54 验收支持

- 来源固定为 NX54V100R014 的完整 SHA-256；不接收 BX54E 或其它版本。
  构建器只改 MP03.1 DTB 的桥接启动参数、标记、SPI NOR 和无线子节点状态，
  原厂内核指令、QCA8337、NAND 和按键配置保留。
- `runtime/layout.c` 定义 NX30 / NX54 布局和备份清单。NX54 两个系统槽为
  `0x900000` / `0x3640000`，每个 `0x2d40000` 字节；APPSBL、BOOTCONFIG
  与 NX30 的偏移和大小一致。返回原厂仍按实读的两个槽偏移处理，**不查布局表**。
- NX54 安装要求布局、MP03.1、CDT machid `0x08040001`、有效 ENV 的
  `productname=NX54`、整个 512 KiB SBL1 的 SHA-256 同时匹配。NX30 的板型
  规则另绑定 NX30 布局；安装层也阻止旧规则包把 HW-A 候选写到 NX54 布局。
- NAND/ECC 候选和 NX30 家族一样取自原厂表：NX54 原厂 APPSBL 的 18 行 NAND 表与
  NX30 原厂表 A1/B 逐字节相同，NX54V100R014 内核的 17 行 NAND ID 表（OOB、ECC）与
  NX30 R012 相同，因此候选 = `nand_schema.runtime_profiles(["B"])` 的 17 种组合
  （`pack/make_rules.py` 的 `NX54_NANDS`，自测核对）。每种组合都必须编译在目标 MBN 的
  NAND 目录里。NX54 不再使用 ECC 实测（evidence）放行；实机验收只覆盖 GigaDevice `c8:11`。
- NX54 备份要求 20 个分区全部存在、偏移与大小正确：15 个启动区分区、
  两个系统槽、`pdt_data`、`pdt_data_1`、`exp`。ZIP 是 ECC 解码后的主区，
  不含 OOB 和无分区尾部；坏块、不可读块按原格式列出并用 FF 填充。
  桥接已经覆盖的原备用系统槽无法在此时恢复为升级前内容。
- NX54 镜像使用 192 MiB `/tmp`（NX30 保留 64 MiB），安装前必须完成备份
  读回校验和 ZIP 传输。设备只能知道传输已完成，用户仍须核对电脑上的 ZIP/SHA-256。
- NX54 外层是 160 字节 H3C 头（版本 NX54V100R999）、单一 `ubi-*` FIT 镜像、
  至少 16 KiB 零尾部。没有外层 `u-boot` 段。Python / JS 注入都保留尾部并
  重算整个载荷的头校验。NX30 继续只有原来的 4 字节对齐，没有额外零尾部；
  若其它型号网页也有 multipart 截断问题，存在截断 FIT 尾端的风险。
- 长按 WPS/Mesh 3 秒调用独立 `bb-oem-return commit-reboot`；NX54 DTB 的
  按键为 GPIO27 / KEY_WPS_BUTTON，实际按键事件与网络可达性仍待实机验收。

规则可从一个 dist 目录重新生成：放入原有四个 `h3c-hw-*.mbn` 和新编的
`h3c-nx54.mbn`，使用 `pack/make_rules.py --auto "$DIST" --nx54 ...`，再用
`pack/make_pack.py --auto "$DIST" ...`。生成器校验 MBN 容器和唯一 NX54
NAND-auto 身份，重新计算文件及 FF 填充分区哈希，不固定 U-Boot 文件哈希。
既有 NAND hold 选项须随发布继续传入。新版规则需要本版含 `layout` / `sbl1.sha256`
谓词的运行时，不能仅把规则包换到旧版基础镜像中。

私有 NX54 测试输入通过环境传入，不进入仓库：

```bash
export TMPDIR="$OUT/tmp"           # 先创建该目录
export BB_RULES="$OUT/rules/rules.txt" BB_PACK="$OUT/rules/rules.bbpack"
export BB_NX54_TEST_OUT="$OUT/nx54-backup.zip"
make test                          # NX54_RAW + 原有 BB_FIXTURES
make arm ARM_CC="${CROSS_COMPILE}gcc"
export BB_BUILDS="$OUT/builds"      # 五款构建目录，含 NX54
python3 tests/test_build.py          # 需要 NX54_OFFICIAL 和上面的构建产物
node web/tests/engine_vs_python.js "$OUT/site" "$OUT/inputs" "$OUT/builds"
node web/tests/e2e.js "$SITE_URL" "$OUT/inputs" "$OUT/builds" "$OUT/e2e-shots"
node tests/device_return_mock.js web-device
```

`NX54_RAW` 是 `mtdN-<name>.a.bin` 原厂主区备份目录；NX54 主机测试从真实 MIBIB
建立模拟 NAND。未设置或清空 `NX54_RAW` 时只跳过 NX54 私有样本测试，可验证原 R4 规则包。
网页 e2e 覆盖 NX30 家族四款和 NX54 共五款。
