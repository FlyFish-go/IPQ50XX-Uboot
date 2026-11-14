---
title: 安装
description: IPQ50XX-Uboot 的几种安装方式，以及各自适用的机型。
---

# 安装

用哪种方式由机型决定，不用自己选。机型页里只写适用于它的那一种。

| 方式 | 适用机型 | 要拆机吗 |
|---|---|---|
| [BootBridge 网页安装](/install/bootbridge) | H3C NX30、RT3000、RC3000、RW3000 | 不用 |
| [TTL 串口安装](/install/ttl) | 其他已验证的机型 | 要 |
| [RAM 试跑](/install/ram-trial) | 未验证的机型，只给测试者 | 要，而且不写闪存 |
| [系统内安装（Telnet / SSH）](/install/shell) | 调研中，还没有对任何机型开放 | 不用 |

这几种方式有两点是一样的：

- 写入前先完整备份闪存。备份里有这台机器的校准数据、MAC 和序列号，只留给自己。
- 两份 U-Boot（`APPSBL` 和 `APPSBL_1`）一起写，写完读回核对，对不上就报错。

先去[机型列表](/devices/)找到你的机器。
