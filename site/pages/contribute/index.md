---
title: 参与收录
description: 机型还没支持怎么办：收录一个机型的流程，以及可以怎么帮忙。
---

# 我的机型还没支持

目标是把大部分 IPQ50xx 路由器都收录进来，但维护者手里的机器有限，很多机型要靠大家帮忙。已经列在[机型列表](/devices/#planned)「规划中」里的，那一栏写了现在卡在哪里。

## 收录一个机型要经过哪几步

1. 收集资料：分区表、闪存型号、安全启动状态、原厂的双系统方式、串口和网口。
2. 写机型资料：每个机型一份数据文件，放在仓库的 `site/devices/` 目录。本站的机型页和安装步骤都从这里生成。
3. 出「未验证」构建：只给能接 TTL 的人做 RAM 试跑。
4. 实机验证：由能接 TTL 的人走完整个流程，状态变成「已验证」或「社区验证」以后，才对普通用户开放。

## 你可以怎么帮忙

- 做 RAM 试跑：手里有「未验证」机型、能接 TTL 的，按 [RAM 试跑](/install/ram-trial)做一遍，提交报告。不写闪存，断电就恢复。
- 提供拿 root 的方法：你的机型怎么在原厂系统里打开 Telnet 或 SSH。这是[系统内安装](/install/shell)的前提。
- 提供只读资料：原厂命令行里 `cat /proc/mtd`、`cat /sys/devices/system/qfprom/qfprom0/authenticate` 的输出，和原厂 U-Boot 里 `printenv` 的输出（先把 MAC、序列号、密码打码）。
- 借机或送机：开 Issue 联系。

::: note 请不要上传
整片闪存备份、ART 分区、原厂固件文件。它们要么含有你这台机器的私有数据，要么有版权问题。我们只需要分区布局、大小和哈希值。
:::

## 反馈入口

[GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues) · [提交试跑报告](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues/new?template=board-report.yml) · QQ 群 1131957442
