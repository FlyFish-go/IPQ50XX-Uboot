---
title: IPQ50XX-Uboot
full_title: IPQ50XX-Uboot：给 IPQ50xx 路由器换一个带网页救援的 U-Boot
description: 给高通 IPQ50xx 路由器换一个带网页救援的 U-Boot，原厂的双系统照常能用。机型列表、安装步骤和救砖方法。
---

# 给 IPQ50xx 路由器换一个带网页救援的 U-Boot

装好以后，系统刷坏了可以进救援页重新刷，不用拆机、不用编程器；原厂的双系统照常能用。
{: .lead}

{{home_finder}}

每个机型有自己的一页，写着这台机器要输入的每条命令、屏幕上应该出现什么、不对的时候怎么办。

## 现在能装的机型

{{verified_table}}

另外有 {{n_untested}} 款有构建、还没人在真机上验证过，只能 RAM 试跑；{{n_planned}} 款在规划中。全部见[机型列表](/devices/)。

## 安装会改动什么

U-Boot 是路由器通电后最先运行的程序之一，由它决定启动哪个系统。闪存里通常放着两份（`APPSBL` 和 `APPSBL_1`），安装就是把这两份换掉，别的分区不碰。

{{fig_flash}}

- 写入前先完整备份闪存。备份里有这台机器的校准数据、MAC 和序列号，只留给自己。
- 两份一起写，写完读回核对，对不上就报错。
- 想回原厂，把备份里的这两个分区写回去就行，见[升级 U-Boot、回原厂](/use/upgrade)。

本项目只做 U-Boot。系统固件用各机型社区维护的 OpenWrt 等；H3C NX30 家族另有配套的 QSDK 和 OpenWrt 固件，见[刷固件与切换系统](/use/firmware)。

## 怎么装

用哪种方式由机型决定，机型页里只写适用于它的那一种。

| 方式 | 适用机型 | 要拆机吗 |
|---|---|---|
| [BootBridge 网页安装](/install/bootbridge) | H3C NX30、RT3000、RC3000、RW3000 | 不用 |
| [TTL 串口安装](/install/ttl) | 其他已验证的机型 | 要 |
| [RAM 试跑](/install/ram-trial) | 未验证的机型，只给测试者 | 要，不写闪存 |

不拆机的[系统内安装](/install/shell)（Telnet / SSH）还在调研。

## 装好以后是什么样

<figure>
<img src="/img/rescue-overview.png" alt="救援页的系统信息页" loading="lazy">
<figcaption>H3C NX30 上的救援页。电脑接网线、打开浏览器就能用，不依赖路由器上装的任何系统。</figcaption>
</figure>

- [进入救援页](/use/rescue)：各机型怎么进、电脑怎么连。
- [刷固件与切换系统](/use/firmware)：刷第三方固件，在两个系统之间切换。
- [升级 U-Boot、回原厂](/use/upgrade)

## 出了问题

先按现象查：[出问题怎么办](/help/)。查不到的，到 QQ 群 1131957442 或 [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues) 问。机型不在列表里，见[参与收录](/contribute/)。
