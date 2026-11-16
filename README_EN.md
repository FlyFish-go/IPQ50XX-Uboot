# IPQ50XX-Uboot

A usable U-Boot for Qualcomm IPQ50xx routers: web recovery, dual boot that follows the vendor's slot logic, and checks before every write.

Install guide (Chinese): <https://flyfish-go.github.io/IPQ50XX-Uboot/>

| Device | Status |
|---|---|
| H3C NX30 / RT3000 / RC3000 / RW3000 | Verified, current release v0.2.0 (one file per hardware group, NAND detected at boot), installed with BootBridge Web |
| Xiaomi CR8806, Lingyan LYW-30M (CUCC VS010), TCL T30 Pro, HW3000B1, Ruijie RG-MA3063, CMCC MR3000D-CI, CMCC RAX3000Q(Y) | Verified, installed over a TTL serial console |
| CMCC PZ-L8, Ruijie RG-MA3063 V3 | Builds, **not tested on hardware, do not flash** (RAM trial only) |
| Most other IPQ50xx boards (Xiaomi AX6000, Redmi AX5400, TP-Link, Linksys, ...) | Planned, no build yet |

The rescue page's firmware update writes only a UBI system image (a `.ubi` file or a backup of a rootfs partition). It does not take vendor upgrade packages: they also carry SBL1, APPSBL and the rest of the boot chain, which the rescue page should not touch, and accepting them would need an allowlist in U-Boot that every vendor release would force us to update. Take the UBI out of a vendor package with the web unpacker, which runs offline in your browser.

First-time H3C installs use BB2-R8 [BootBridge Web](https://flyfish-go.github.io/IPQ50XX-Uboot/bootbridge/), which directly installs the final v0.2.0 release. Releases up to v0.1.0 are at [H3C-NX30-Uboot](https://github.com/FlyFish-go/H3C-NX30-Uboot/releases); later releases are published here. NX54 is listed as testing (`site/data/bootbridge.json`: `nx54=hidden|testing`).

Build instructions: [BUILDING.md](BUILDING.md). Based on [chenxin527/uboot-qsdk12.5-build](https://github.com/chenxin527/uboot-qsdk12.5-build) (uBootKit); see [LICENSE](LICENSE) and [LICENSE-NOTICE.md](LICENSE-NOTICE.md).

This project is not affiliated with any router vendor.

## Support

This is a one-person hobby project; code and firmware stay free. If it helped you, you can chip in on [Afdian](https://ifdian.net/a/FlyFish-go) or via [WeChat / Alipay](docs/sponsor.md). Money goes to new devices and debug tools; it does not buy a promise to support any model. Lending or donating a device is just as welcome — open an issue.
