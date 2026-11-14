---
title: IPQ50XX-Uboot
full_title: IPQ50XX-Uboot：给 IPQ50xx 路由器换一个带网页救援的 U-Boot
description: 给高通 IPQ50xx 路由器换一个带网页救援的 U-Boot，原厂的双系统照常能用。机型列表、安装步骤和救砖方法。
---

# IPQ50XX-Uboot

给高通 IPQ50xx 路由器换一个带网页救援的 U-Boot。装好以后，系统刷坏了可以进救援页重新刷，原厂的双系统照常能用。

本项目只做 U-Boot。系统固件用各机型社区维护的 OpenWrt 等；H3C NX30 家族另有配套的 QSDK 和 OpenWrt 固件。

## 现在能装的机型

{{verified_table}}

另外有 {{n_untested}} 款有构建、还没人在真机上验证过，只能 RAM 试跑；{{n_planned}} 款在规划中。全部见[机型列表](/devices/)。

## 怎么装

- H3C NX30、RT3000、RC3000、RW3000：不用拆机，用 [BootBridge 网页安装](/install/bootbridge)。
- 其他已验证的机型：拆机接串口，用 [TTL 串口安装](/install/ttl)。每台机器的命令写在它的机型页里。
- 不拆机的[系统内安装](/install/shell)（Telnet / SSH）还在调研。

不管用哪种方式，写入前都要先完整备份闪存；两份 U-Boot 一起写，写完读回核对。

## 装好以后

- [进入救援页](/use/rescue)
- [刷固件与切换系统](/use/firmware)
- [升级 U-Boot、回原厂](/use/upgrade)

## 出了问题

先按现象查：[出问题怎么办](/help/)。查不到的，到 QQ 群 1131957442 或 [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues) 问。

## 其他

- [双系统怎么切换](/learn/slots)
- [名词解释](/learn/glossary)
- [我的机型不在列表里](/contribute/)
- [关于本项目](/about)
