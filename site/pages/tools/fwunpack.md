---
title: 离线固件拆包
description: 在自己的浏览器中从厂商包或 OpenWrt 固件取出裸 UBI，供救援页刷入。不上传文件。
---

# 离线固件拆包

把自己下载的固件放进来，取出里面的 **UBI 系统镜像**。文件只在你的浏览器里处理，不上传、不联网，也不会连接路由器。

救援页的「固件更新」只接收裸 UBI。厂商包还可能带着 SBL1、U-Boot 等启动链；这个工具只取系统 UBI，不导出其他分区。[为什么只收 UBI](/use/firmware#只收-ubi)

## 选择固件

{{fwunpack}}

## 哪些文件能处理

按文件结构识别，不按固件版本或哈希名单识别。同一种结构的新版本可直接处理；结构变了或校验失败会给出原因。hash 和 CRC 用于检查文件完整性，不验证厂商签名或来源。

| 文件 | 处理方式 |
|---|---|
| H3C NX30 家族、NX54 的原厂 `.bin` | 跳过 H3C 头，从 FIT 的系统段取出 UBI |
| GL.iNet GL-B3000 原厂包 | 按 FIT 处理；已验证 4.5 和 4.7 的原厂封装 |
| ELECOM WRC-X3000GS2 / I-O DATA WN-DAX3000GR 的 OpenWrt factory | 校验产品头 / CMOC 长度和 CRC，再取 FIT 中的 UBI；未验证这两家的原厂包 |
| QSDK / 通用 FIT `.img`、`.itb` | 检查 FIT 段内自带的 hash，取唯一的 UBI 系统段；内嵌 data 已用真实包验证；外置 data 路径已实现并通过合成测试，尚无真实样本验证 |
| 小米 HDR1 原厂包 | 校验段表和整包 CRC，处理 root.ubi；已验证 CR8806/8808/8809、RA81、RD03v2；其中嵌套 FIT 的路径仅合成验证 |
| 集客 GecoOS IPQ50XX | 按 FIT 处理；部分 NOR 包没有 UBI，会说明原因。厂商修改的 SquashFS 显示「无法识别」 |
| 锐捷 MA3063 原厂包 | 跳过锐捷头，处理 FIT 中的 UBI；已验证 wuhu、wuhu3 |
| OpenWrt sysupgrade tar | root 已是 UBI 或 FIT 时继续拆；标准 SquashFS 则用 kernel 和 root 生成 UBI |
| 裸 `.ubi` 或 rootfs 分区备份 | 校验后原样输出，不裁剪、不改写 |

GL.iNet、京东云和 ASUS 的品牌名称本身不能说明包里有 UBI。仅含独立内核、NOR 或 eMMC 文件系统的包不能用这个工具转换。其他封装、小米 HDR2、压缩包和加密包尚未验证。

## sysupgrade 转成 UBI

NAND sysupgrade 包里的 `root` 通常只是 SquashFS，并不是可直接刷入的 UBI。工具使用固定配置生成三个 dynamic 卷：`kernel`、`rootfs`、`rootfs_data`，最后一个卷自动扩展。它不保留旧系统设置。

```text
PEB（擦除块）     131072 字节
页 / VID 偏移       2048 字节
数据偏移            4096 字节
LEB（逻辑块）     126976 字节
image_seq / EC          0 / 0
```

参数来自本项目救援端 `firmware_rt3000_b.c` 的 NAND 配置，与 OpenWrt qualcommax 常用的 `BLOCKSIZE=128k`、`PAGESIZE=2048` 相同。JS 输出已与同参数的 mtd-utils `ubinize` 比较。**几何相同仍不代表启动方式相同**：目标需要从 UBI 的 `kernel` 和 `rootfs` 卷启动。使用独立内核分区、不同 NAND 几何或 eMMC 的机型不适用。

## 下载后怎么刷

1. 保留原文件和拆出的 `.ubi`，核对页面上的卷表、内核信息和容量提示。
2. [进入本项目救援页](/use/rescue)，打开「固件更新」。
3. 选择拆出的 `.ubi`，确认系统槽和救援页校验结果，再写入。双系统机型可以把原来的系统留在另一个槽。

机型检查只作提示。工具看不见设备上的坏块，也不能替你确认当前分区布局。刷错系统可能无法启动，可以重新进入救援页刷回正确 UBI。

::: danger 不要在原厂系统里在线升级
厂商升级可能改写另一套 SBL1 / APPSBL 启动链，切换过去后会失去本项目的救援页。要换原厂版本，先在这里拆出 UBI，再从救援页刷入。详见[升级说明](/use/firmware#原厂系统里的升级)。
:::

## 离线保存

完整保存构建好的站点目录，直接打开 `tools/fwunpack.html` 就能使用。需要一起保存 `style.css`、`site.js`、`fwunpack/core.js` 和 `fwunpack/app.js`；只有一个 HTML 文件不够。解析、校验、生成和下载都在本机完成。
