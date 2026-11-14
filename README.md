# IPQ50XX-Uboot

给高通 IPQ50xx 路由器装一个好用的 U-Boot：网页救砖、照原厂逻辑的双系统、写入前逐项核对。

安装指南网站：<https://flyfish-go.github.io/IPQ50XX-Uboot/>

## 支持情况

| 机型 | 安装方式 |
|---|---|
| H3C NX30 / RT3000 / RC3000 / RW3000 | 已验证，[BootBridge 网页版](https://flyfish-go.github.io/H3C-NX30-Uboot/)安装，不用拆机 |
| 小米 CR8806、领研 LYW-30M（联通 VS010）、TCL T30 Pro、航芯 HW3000B1、锐捷 RG-MA3063、中国移动 MR3000D-CI | 已验证，TTL 串口安装 |
| 中国移动 RAX3000Q、PZ-L8，锐捷 RG-MA3063 V3 | **未验证，请勿刷入**，只做 RAM 试跑 |
| 其余大部分 IPQ50xx 机型（小米 AX6000、红米 AX5400、TP-Link、Linksys 等） | 规划中，还没有构建 |

每个机型的安装步骤、下载和验证情况以[安装指南网站](https://flyfish-go.github.io/IPQ50XX-Uboot/devices/)为准，规划中的机型在那里写了现在缺什么。不拆机的「系统内安装（Telnet / SSH）」还在调研。

H3C 机型的 v0.1.0 及更早版本在 [H3C-NX30-Uboot](https://github.com/FlyFish-go/H3C-NX30-Uboot/releases) 下载，之后的版本在本仓库发布。

## 目录

| 路径 | 内容 |
|---|---|
| `u-boot-2016/` | U-Boot 源码，保留上游布局 |
| `build-release.sh`、`release-tools/` | 发布构建与封装工具，说明见 [BUILDING.md](BUILDING.md) |
| `docs/`、`releases/` | H3C 机型的文档和历史发布说明 |
| `tools/` | BootBridge 等配套工具 |
| `site/` | 安装指南网站：`site/build.py` 把下面的资料生成纯静态页面 |
| `site/devices/` | 每个有构建的机型一份资料（YAML），网站和安装程序都从这里读取 |
| `site/data/` | 规划中和不打算做的机型（`others.yaml`）、已正式发布的构建（`releases.yaml`） |
| `site/pages/` | 网站的文字页面（Markdown） |

## 本地预览网站

```sh
pip install -r site/requirements.txt
python3 site/build.py
python3 -m http.server -d site/dist 8000
```

浏览器打开 <http://localhost:8000/>。构建时会检查所有站内链接和锚点，坏了就报错。

## 添加一个机型

复制 `site/devices/` 下一个现有文件，改成新机型的资料，文件名与 `id` 一致。字段说明见 `site/build.py` 开头，要点：

- `status`：`verified`、`community`、`untested` 之一；`untested` 的 `artifact` 必须以 `-untested` 结尾。
- `install.method`：`bootbridge` 或 `ttl`。安装步骤不写在 YAML 里，由 `site/build.py` 的 `ttl_steps()`、`web_steps()` 按安装方式生成。
- `brief`：机型列表里的一行说明。
- `ttl`：样机上实测的串口电平、引脚、截停方法、设备树地址（`fdt`）等，没人测过的就不写。
- `notes.<步骤 id>`：只对这个机型的补充说明，显示在对应步骤里（步骤 id 见 `build.py` 的 `STEP_IDS`）。
- `shell.access`：在原厂系统里拿 root 的线索（系统内安装用）。

还没有构建的机型不建 YAML，写进 `site/data/others.yaml`：`planned`（规划中，写明还缺什么）或 `wontdo`（不打算做，写明原因）。

正式发布某个构建后，在 `site/data/releases.yaml` 里登记，机型页的下载就会指向发布页。

## 支持项目

本项目由个人业余维护，代码和固件始终免费公开。如果它帮到了你，可以在 [爱发电](https://ifdian.net/a/FlyFish-go) 或用 [微信 / 支付宝](docs/sponsor.md) 支持一下。捐款用于购买新机型和调试工具（TTL、编程器等），不对应任何机型的适配承诺或时间，采购记录见[支持页面](docs/sponsor.md)。也欢迎借机、送机，请开 issue 联系。

## 来源与许可

本项目基于 [chenxin527/uboot-qsdk12.5-build](https://github.com/chenxin527/uboot-qsdk12.5-build)（uBootKit），感谢 chenxin527 及 uBootKit 的上游贡献者，以及为上游 README 贡献过的 webbrain-one。上游的完整提交历史保留在 [H3C-NX30-Uboot](https://github.com/FlyFish-go/H3C-NX30-Uboot)。许可见 [LICENSE](LICENSE) 和 [LICENSE-NOTICE.md](LICENSE-NOTICE.md)。

本项目与各路由器厂商无关。
