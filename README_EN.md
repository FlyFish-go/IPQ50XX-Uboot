# IPQ50XX-Uboot

A usable U-Boot for Qualcomm IPQ50xx routers: web recovery, dual boot that follows the vendor's slot logic, and checks before every write.

Install guide (Chinese): <https://flyfish-go.github.io/IPQ50XX-Uboot/>

| Device | Status |
|---|---|
| H3C NX30 / RT3000 / RC3000 / RW3000 | Verified, current release v0.1.0 |
| Lingyan LYW-30M, CUCC VS010 / VS010 MAX | Builds, **not tested on hardware, do not flash** |
| TCL T30 Pro | Builds, **not tested on hardware, do not flash** |

First-time H3C installs use [BootBridge Web](https://flyfish-go.github.io/H3C-NX30-Uboot/). Releases up to v0.1.0 are at [H3C-NX30-Uboot](https://github.com/FlyFish-go/H3C-NX30-Uboot/releases); later releases are published here.

Build instructions: [BUILDING.md](BUILDING.md). Based on [chenxin527/uboot-qsdk12.5-build](https://github.com/chenxin527/uboot-qsdk12.5-build) (uBootKit); see [LICENSE](LICENSE) and [LICENSE-NOTICE.md](LICENSE-NOTICE.md).

This project is not affiliated with any router vendor.
