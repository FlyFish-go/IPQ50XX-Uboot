---
title: 关于本项目
description: IPQ50XX-Uboot 的来历、致谢、许可和免责声明。
---

# 关于本项目

IPQ50XX-Uboot 从 [H3C-NX30-Uboot](https://github.com/FlyFish-go/H3C-NX30-Uboot) 发展而来。那个项目给 H3C NX30、RT3000、RC3000、RW3000 做了带网页救砖和双系统的 U-Boot。现在把它扩展到更多高通 IPQ50xx 路由器：每个机型一份配置，共用同一套 U-Boot 和同一个安装指南。

源码在 [GitHub](https://github.com/FlyFish-go/IPQ50XX-Uboot)。

## 了解更多

- [双系统怎么切换](/learn/slots)
- [名词解释](/learn/glossary)
- [参与收录](/contribute/)

## 致谢

- [chenxin527/uboot-qsdk12.5-build](https://github.com/chenxin527/uboot-qsdk12.5-build)（uBootKit）及其上游贡献者：U-Boot 与救援页的基础。
- [OpenWrt](https://openwrt.org/) 上游各机型的移植者：分区布局、双系统机制和安装方法的大量资料来自他们的工作。
- [ayu1808](https://github.com/ayu1808)：H3C 项目的适配思路与大量测试。
- 所有帮忙测试、反馈的群友。

## 支持项目

本项目由个人业余维护，代码和固件始终免费公开。如果它帮到了你，可以在[爱发电](https://ifdian.net/a/FlyFish-go)支持一下。捐款用于购买新机型和调试工具（TTL、编程器等），不对应任何机型的适配承诺或时间。也欢迎借机、送机，请开 Issue 联系。

## 许可

U-Boot 和第三方组件保留原有许可证与版权（GPL-2.0 等）。本站引用其他教程时注明出处，只放链接，不转载别人的工具和固件。

## 免责声明

本项目与 H3C、小米、锐捷、中国移动、TCL 及其他路由器厂商无关。改写启动程序有变砖风险，请只按「已验证」机型的步骤操作，风险自负。
