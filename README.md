# IPQ50XX-Uboot

给高通 IPQ50xx 路由器装一个好用的 U-Boot：网页救砖、照原厂逻辑的双系统、写入前逐项核对。

安装指南网站：<https://flyfish-go.github.io/IPQ50XX-Uboot/>

## 支持情况

| 机型 | 状态 |
|---|---|
| H3C NX30 / RT3000 / RC3000 / RW3000 | 已验证，当前版本 v0.1.0 |
| LYW-30M、联通 VS010 / VS010 MAX | 可以构建，**尚未上机测试，请勿刷入** |
| TCL T30 Pro | 可以构建，**尚未上机测试，请勿刷入** |

H3C 机型的首次安装请用 [BootBridge 网页版](https://flyfish-go.github.io/H3C-NX30-Uboot/)。v0.1.0 及更早的版本在 [H3C-NX30-Uboot](https://github.com/FlyFish-go/H3C-NX30-Uboot/releases) 下载，之后的版本在本仓库发布。

## 目录

| 路径 | 内容 |
|---|---|
| `u-boot-2016/` | U-Boot 源码，保留上游布局 |
| `build-release.sh`、`release-tools/` | 发布构建与封装工具，说明见 [BUILDING.md](BUILDING.md) |
| `docs/`、`releases/` | H3C 机型的文档和历史发布说明 |
| `tools/` | BootBridge 等配套工具 |
| `site/` | 安装指南网站（VitePress） |
| `site/devices/` | 每个机型一份资料（YAML），网站和安装程序都从这里读取 |

## 本地预览网站

```sh
cd site
npm ci
npm run docs:dev
```

## 添加一个机型

复制 `site/devices/` 下一个现有文件，改成新机型的资料，文件名与 `id` 一致。`status` 只能是 `verified`、`community`、`testing`、`planned` 之一。

## 支持项目

本项目由个人业余维护，代码和固件始终免费公开。如果它帮到了你，可以在 [爱发电](https://ifdian.net/a/FlyFish-go) 或用 [微信 / 支付宝](docs/sponsor.md) 支持一下。捐款用于购买新机型和调试工具（TTL、编程器等），不对应任何机型的适配承诺或时间，采购记录见[支持页面](docs/sponsor.md)。也欢迎借机、送机，请开 issue 联系。

## 来源与许可

本项目基于 [chenxin527/uboot-qsdk12.5-build](https://github.com/chenxin527/uboot-qsdk12.5-build)（uBootKit），感谢 chenxin527 及 uBootKit 的上游贡献者，以及为上游 README 贡献过的 webbrain-one。上游的完整提交历史保留在 [H3C-NX30-Uboot](https://github.com/FlyFish-go/H3C-NX30-Uboot)。许可见 [LICENSE](LICENSE) 和 [LICENSE-NOTICE.md](LICENSE-NOTICE.md)。

本项目与各路由器厂商无关。
