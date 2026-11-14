# IPQ50XX-Uboot

A usable U-Boot for Qualcomm IPQ50xx routers: web recovery, dual boot that follows the vendor's slot logic, and checks before every write.

Install guide (Chinese): <https://flyfish-go.github.io/IPQ50XX-Uboot/>

| Device | Status |
|---|---|
| H3C NX30 / RT3000 / RC3000 / RW3000 | Verified, current release v0.1.0, installed with BootBridge Web |
| Xiaomi CR8806, Lingyan LYW-30M (CUCC VS010), TCL T30 Pro, HW3000B1, Ruijie RG-MA3063, CMCC MR3000D-CI | Verified, installed over a TTL serial console |
| CMCC RAX3000Q, CMCC PZ-L8, Ruijie RG-MA3063 V3 | Builds, **not tested on hardware, do not flash** (RAM trial only) |
| Most other IPQ50xx boards (Xiaomi AX6000, Redmi AX5400, TP-Link, Linksys, ...) | Planned, no build yet |

First-time H3C installs use [BootBridge Web](https://flyfish-go.github.io/H3C-NX30-Uboot/). Releases up to v0.1.0 are at [H3C-NX30-Uboot](https://github.com/FlyFish-go/H3C-NX30-Uboot/releases); later releases are published here.

Build instructions: [BUILDING.md](BUILDING.md). Based on [chenxin527/uboot-qsdk12.5-build](https://github.com/chenxin527/uboot-qsdk12.5-build) (uBootKit); see [LICENSE](LICENSE) and [LICENSE-NOTICE.md](LICENSE-NOTICE.md).

This project is not affiliated with any router vendor.

## Support

This is a one-person hobby project; code and firmware stay free. If it helped you, you can chip in on [Afdian](https://ifdian.net/a/FlyFish-go) or via [WeChat / Alipay](docs/sponsor.md). Money goes to new devices and debug tools; it does not buy a promise to support any model. Lending or donating a device is just as welcome — open an issue.
