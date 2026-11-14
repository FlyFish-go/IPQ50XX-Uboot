---
title: RAM 试跑
description: 给未验证机型的测试者：把 U-Boot 加载到内存里运行一次，不写闪存，断电就恢复。
---

# RAM 试跑

「未验证」的机型还没有人在真机上跑过。RAM 试跑就是把本项目的 U-Boot 加载到内存里运行一次：全程不写闪存，断电就恢复原样。一块板要靠试跑报告才能改成「已验证」。

<p class="caution">试跑成功不代表可以刷入，它只是让这块板第一次有了真机反馈。维护者确认改成「已验证」之前，请不要把 U-Boot 写进闪存。</p>

## 现在等人试跑的机型

{{trial_list}}

每个机型页都有一份按它的情况写好的步骤，命令可以直接复制。

## 需要什么

- 能接 TTL 串口。接线、电平、电脑设置见 [TTL 串口安装](/install/ttl)；
- 一台电脑做 TFTP 服务器，网线接路由器的 LAN 口，电脑 IP 设成 `192.168.1.2`；
- 对应机型的试跑文件 `<构建名>-untested-ram.uimg`，下载方法在机型页开头的表格里。

## 大致步骤

1. 截停原厂 U-Boot：通电后在 `Hit any key to stop autoboot` 时按回车；
2. 记下设备树地址：`printenv fdtcontroladdr`，没有这个变量就看 `bdinfo` 的 `fdt_blob` 一行。每种机型不一样，不要照抄别人的地址；
3. 传文件并启动（最后一行换成你的地址）。这里必须用 `bootm`，原厂 U-Boot 不允许直接跳到内存里的程序；
4. 看新 U-Boot 起来没有：串口出现本项目的启动信息，并且有一行 `UNTESTED BOARD: not verified on hardware`；
5. 打开救援页：新 U-Boot 倒计时时再按一次回车，输入 `httpd`，浏览器打开 `http://192.168.1.1`；
6. 断电：重新上电，路由器按原样启动原厂系统。

第 3 步的命令：

```
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.2
tftpboot 0x44000000 <构建名>-untested-ram.uimg
bootm 0x44000000 - <上一步的地址>
```

## 要记录什么

- 串口有没有出本项目的启动信息，有没有 `UNTESTED BOARD` 那一行；
- 闪存型号和 ECC 识别那几行；
- 每个网口：插上网线有没有 link，电脑能不能 ping 通 `192.168.1.1`，能不能打开救援页（一次只接一根网线）；
- 救援页「系统信息」里显示的内容；
- 按 Reset、WPS / Mesh 键有没有反应；每个 LED 亮不亮、什么颜色。

::: danger 只看，不写
不要点救援页里「写入」「更新」一类的按钮，也不要在串口里执行 `saveenv`、`nand write`、`bootconfig set` 之类的命令。
:::

## 提交报告

测完不管成功还是失败，都请[提交试跑报告](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues/new?template=board-report.yml)：机型、机身贴纸上的硬件版本、启动日志、闪存型号、救援页结果、LED 和按键。

启动日志里的 MAC 地址、序列号、密码先打码。请不要上传整片闪存备份、ART 分区或原厂固件。
