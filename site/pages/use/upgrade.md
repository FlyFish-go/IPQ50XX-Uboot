---
title: 升级 U-Boot、回原厂
description: 在救援页里升级 IPQ50XX-Uboot，以及怎么回到原厂系统或原厂 U-Boot。
---

# 升级 U-Boot、回原厂

## 升级 U-Boot

装过本项目 U-Boot 的机器，升级都在救援页「U-Boot 更新」里完成：上传新版本的文件，两份 APPSBL 一起写入，写完读回核对，断电重启后看版本号。

### H3C NX30 家族

1. 进救援页，在「系统信息」里看「硬件系列」（HW-A、B、C、D）；
2. 到 [v0.1.0 发布页](https://github.com/FlyFish-go/H3C-NX30-Uboot/releases/tag/uboot-v0.1.0)下载对应的 `uboot-v0.1.0-HW-X.zip`；
3. 压缩包里按闪存型号分了文件夹。v0.1.0 的救援页会直接告诉你该选哪个 `appsbl.mbn`；从更早的版本升级时，按发布说明「升级」一节找文件；
4. 在「U-Boot 更新」上传，等写完，断电重启。

::: note HW-D 的旧版本
HW-D 上 ECC 8 位的机器，如果还在 pre.5 或更早的版本，直接「U-Boot 更新」会失败，要先用 RAM 救援版过渡。步骤见 [pre.7 说明](https://github.com/FlyFish-go/H3C-NX30-Uboot/blob/main/releases/uboot-v0.1.0-pre.7.md#从-pre3pre6-升级)。
:::

### 其他机型

到机型页开头表格里的「下载」拿新的 `<构建名>.mbn`，在救援页「U-Boot 更新」上传。只用本机型的文件，页面拒绝时不要换别的机型的文件硬刷。

## 回原厂

先想清楚要回到哪一步。

### 只想用原厂系统

双系统机型的原厂系统一直留在其中一个区，在救援页或用按键切过去就行，U-Boot 不用动。原厂系统自己的在线升级照常能用。

### 连 U-Boot 也换回原厂的

这要把安装前备份的原厂 U-Boot 分区写回去：

- H3C：用 BootBridge 安装时保存的备份；
- 其他机型：用安装前在救援页下载的整片闪存备份。

写回启动分区出错就可能变砖，而且各机型的分区位置不一样。请先到 QQ 群 1131957442 或 [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues) 说明情况，确认步骤后再动手，手边最好有 TTL。

::: note 备份只能用在原来那台机器上
备份里有这台机器的校准数据（ART）、MAC 地址和序列号。拿别人的备份或者自己另一台的备份写进去，Wi-Fi 校准和 MAC 会错。
:::
