---
title: 仅收录资料与不做的机型
outline: [2, 3]
---

# 仅收录资料与不做的机型

这一页列的机型**都没有可用的 U-Boot**，请不要尝试刷入。它们分两类：只整理了公开资料的（状态「仅收录资料」），和因为技术原因暂时不做的。

有人需要某个机型、并且分区表、串口、网口、环境变量位置这几项都找得到来源时，可以升级成「未验证」再出构建，见[参与收录](/contribute/)。

## 仅收录资料

状态：<StatusBadge status="research" />　本轮没有构建，也没有设备树。

| 机型 | 已知情况 | 还缺什么 |
|---|---|---|
| 京东云 AX3000 | 闪存是 eMMC（GPT 分区），不是 NAND。我们所有已验证的槽位和刷写流程都建立在 NAND 上 | 环境变量位置、分区表、实物备份。先要有人提供 eMMC 备份 |
| 移动 MR3000D-04 | 只有第三方一份「继承 MR3000D-CI」的设备树。「128 MiB 闪存版」不能区分它和 -CI（-CI 本身就是 128 MiB） | -04 和 -CI 的真实差异、实物备份 |
| 电信 AP301-L | 没有任何实物证据。同一个 machid 的 LYW-30M 用的是 QCA8337，而它用的是另一种网络芯片（NAPA PHY），不能靠 machid 选网络配置 | 内存、闪存、槽位、环境变量 |
| SKSPRUCE AP8330C | 同上，网口的 gmac 方向和别的机型相反 | 同上 |
| 锐捷 RG-MA3063 V4 / RG-MA3064 | 原厂 CDT 为 `AP-MP03.5-C2`（machid `0x8040104`）。没有这个版本的设备树 | 串口、网口、LED、按键。V3 见[单独页面](/devices/ruijie-rg-ma3063-v3) |
| 小米 AX6000 | 上游 OpenWrt 有设备树。内存 512 MiB，串口 1.8 V，部分单元闪存要 ECC 8 位，QCA8081 后面还接了交换芯片，这个网络布局我们的树里没有 | 安全启动状态必须先查，网络配置要新写 |
| 红米 AX5400 | 上游 OpenWrt 有设备树。GE PHY 和 SGMII 同时进入 QCA8337。原厂 U-Boot 里有 `is_sec_boot_enabled` | 安全启动状态（安装前必须查 qfprom）、实物备份 |
| ELECOM WRC-X3000GS2 / GST2、I-O DATA WN-DAX3000GR | 分区表和 PZ-L8 几乎一样，BOOTCONFIG 加 QCA8337 | 实物资料 |
| 中兴 T5400、Zyxel SCR50AXE、Xunison D50、GL.iNet GL-X2000 | 只知道是 IPQ5018 / IPQ5000 机型 | 几乎全部 |
| Yuncore AX830 / AX850、Wallys DR5018S | 用 QCA8081 | 几乎全部 |
| Davolink DVW-632X | 拿原厂 root 的方法要到 2027-01-27 才公开 | 等披露 |

## 不做的机型

这些机型现在做不了，写明原因，免得有人白白尝试。

| 机型 | 原因 |
|---|---|
| 小米 CR881x、CR8818、小米 AX3000T v2 | 交换芯片是 YT9215S 或 AN8855，U-Boot 里没有驱动 |
| TP-Link Archer AX55 v1、EAP650、RE700X，Mercusys MR80X v2 | 要用 `tp_boot_idx` 环境变量切换系统，这个后端还没写 |
| Linksys MR / MX / SPNMX56 系列 | 要用 `boot_part` 环境变量，后端还没写；MX6200 还开了安全启动 |
| Netgear WAX630E | 需要 `boot_count` 后端 |
| GL.iNet GL-B3000 | 原厂 U-Boot 自带网页救援，收录价值低（不收） |
| Lite-On WPX8324 | 从 SPI NOR 启动，和本项目的 NAND 流程不同 |
| UniFi 6 Pro、AVM 4050 | 用厂商自己的引导程序，不是 QSDK U-Boot |

`tp_boot_idx`、`boot_part`、`boot_count` 都只是简单的环境变量后端，等有测试者时再写。

## 相关页面

- [支持的设备](/devices/)：所有已验证和未验证的机型
- [参与收录](/contribute/)：怎么提供资料、怎么做 RAM 试跑
