# 公开网页的固定输入

`BB2-R6/` 是可提交的发布资产，不是桥接固件。`SHA256SUMS` 固定 25 个文件：

- 两套规则的 `.txt` / `.bbpack`：NX30-only 与 NX30 + 测试 NX54；
- 五款各一份 `plan.json`、`plan.bin`、`layout.json`、`provenance.json`；
- `release.json`。

完整官方包、`bridge-base.bin`、`bridge.bin`、UBI、SquashFS、样机备份和日志禁止放进这个目录。生成器按严格文件白名单和 SHA256SUMS 验证它，额外文件也会导致构建失败。

这些输入依赖受支持的精确官方固件，必须在维护者的私有构建环境生成并审阅；GitHub Actions 无需也不会下载官方固件。计划只使用 COPY 和 LITERAL：所有原厂内核/DT/用户态压缩数据都从用户所选官方包复制；每个字面量记录自身 SHA256、输出/数据偏移及自有文件或生成元数据的来源。不发布旧 LAB 编译器产生的 XOR 掩码。

发布构建步骤（路径均由调用者提供）：

1. 用正式 U-Boot dist 的 SHA256SUMS 核对四个 MBN，使用 `pack/make_rules.py --auto DIST --release v0.2.0 --set BB2-R6` 生成规则；测试变体另加 `--nx54`。继续保留已审查 NAND hold。
2. 对 ARM 程序执行交叉工具链的 `strip --strip-debug`，保留程序代码；以 `build/build_bridge.py --public-plan` 构建五款。该方式复制原压缩块，重建小型 SquashFS 的元数据，不重新压缩任何原厂文件。
3. 运行 `check_image.py`、`tests/audit_public.py`、JS/Python 与浏览器测试。独立审计必须核对全部原厂/自有文件、每个原厂压缩块的 COPY 来源、全部字面量，并扫描原始及解码公开资产。
4. 用 `web/prepare_release.py --builds BUILDS --rules RULES --out RELEASE` 只复制白名单，人工复核审计后更新这个目录及 SHA256SUMS。`RULES` 需要 `rules{,-nx54}.{txt,bbpack}`。

纯公开输入的构建：

```sh
python3 tools/bootbridge2/web/build_site.py \
  --release-dir tools/bootbridge2/web/release/BB2-R6 \
  --config site/data/bootbridge.json --out PUBLIC_SITE
python3 site/build.py
```

指南站通过 `site/bootbridge.py` 集中调用生成器，路径为 `/IPQ50XX-Uboot/bootbridge/`。`site/data/bootbridge.json` 唯一开关 `nx54` 可为 `hidden`（默认：无机型卡/计划/候选）或 `testing`（显示测试标记并选择含 NX54 的规则包）。没有把测试版写成正式放行；切换配置无需私有输入。

旧站跳转页由维护者单独更新，旧 Release 附件继续保留。
