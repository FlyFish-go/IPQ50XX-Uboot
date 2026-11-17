---
title: 系统内安装（Telnet / SSH）
description: 不拆机、在原厂系统里安装 U-Boot 的计划和进展。还在调研，没有对任何机型开放。
---

# 系统内安装（Telnet / SSH）

系统内安装程序还在调研，没有对任何机型开放。[RG-MA3063 的原厂 SSH 入口已实测](#ma3063-stock-shell)，取得 root 后如何安装 U-Boot 仍须单独验证。现在要装，按机型页上写的方式：H3C 用 [BootBridge 网页安装](/install/bootbridge)，其他机型用 [TTL 串口安装](/install/ttl)。这一页说明这种方式打算怎么做、进展到哪里。

## 是什么

不用拆机：在原厂系统里打开 Telnet 或 SSH，拿到 root 命令行，运行我们的安装程序。安装程序自己核对这台机器、备份、写入 U-Boot、读回核对，任何一项不对就停下。

这是将来给普通用户的主要安装方式。TTL 只留给每个机型的第一位验证者，以及出了问题需要救砖的时候。

## 为什么还没开放

- 每个机型拿 root 的方法都不一样：有的原厂自带 SSH，有的要靠社区工具，有的要利用原厂网页的漏洞，有的根本没有公开方法；
- 原厂内核可能把 U-Boot 所在的分区设成只读，这时从系统里写不进去，要先确认；
- 从系统里写坏了，没有串口就救不回来。所以每个机型都要先有人用 TTL 实机走通、确认能救，再对普通用户开放。

## 安装程序会核对什么

写入之前，下面每一项都要对得上，否则拒绝写入：

1. 机型和主板标识（machid）与机型资料一致；
2. 闪存型号在支持列表里；
3. 分区表的名字、大小、偏移和机型资料一致；
4. 安全启动没有开启：`/sys/devices/system/qfprom/qfprom0/authenticate` 必须是 `0`；
5. U-Boot 所在分区能读、能写。

然后先把原有的 U-Boot 分区备份出来让你保存，再写入，写完逐字节读回核对。

## 各机型的进展

{{shell_table}}

## RG-MA3063：开启原厂 SSH { #ma3063-stock-shell }

RG-MA3063 硬件 1.00 样机已通过工厂接口开启原厂系统的 SSH，以 `admin` 登录后确认是 Linux root。

### 开启与登录

1. 拔掉 WAN 网线，电脑用网线连接设备的 LAN 口，先确认能打开原厂管理页。默认地址为 `192.168.10.1`，改过地址的使用当前地址。此接口会开启调试服务，使用公开工厂口令，请在隔离的管理网络内操作。
2. 浏览器访问 `http://192.168.10.1/__factory_verify_mode__`。样机返回：

   ```json
   {"result": "Pass"}
   ```

3. 在电脑终端连接 SSH：

   ```sh
   ssh -o HostKeyAlgorithms=+ssh-rsa admin@192.168.10.1
   ```

   首次连接先核验并保存主机密钥，密码输入公开工厂口令 `wifi@cmcc`。样机的旧版 Dropbear 需要上述 `ssh-rsa` 主机密钥兼容选项。
4. 登录后执行 `id`。样机实测输出：

   ```text
   uid=0(root) gid=0(root)
   ```

   登录名虽然是 `admin`，实际权限是 root。随后可以运行 `cat /proc/mtd` 等只读检查；本节不包含安装或分区写入命令。

### 验证范围

- 样机资料：硬件 1.00，AP-MP02.1，machid `0x8040000`。本次读取的系统标识为 `wuhu-cmcc-main`，内核为 `4.4.60`，编译时间为 2022-01-13；本次没有重新核对完整原厂固件版本号。
- 开启前 22/23 端口均拒绝连接；接口返回成功后两者开放，SSH 登录和 root 权限已确认。Telnet 只确认了端口开放，没有验证登录。
- 样机此前已刷入本项目 U-Boot，仍运行锐捷原厂系统；本次没有恢复原厂 U-Boot。因此只验证了原厂系统的网络入口，没有验证完整原厂引导链上的首次安装。
- 没有重启或断电，SSH/Telnet 的重启持久性未知。没有测试 V3、V4、MA3064 或其他固件版本。
- 取得 root 不代表系统内安装已通过验收。MA3063 当前安装方式仍见[机型页](/devices/ruijie-rg-ma3063)。

方法来源：[锐捷 RG-MA3063 开启 SSH 的方法](https://blog.kokomi.me/posts/enable-ssh-for-rg-ma3063/)。以上范围内的结果已由项目维护者在样机上复现。

## 你能帮什么忙

- 告诉我们拿 root 的方法：你的机型怎么在原厂系统里打开 Telnet 或 SSH，附上来源链接，发到 [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues)；
- 提供只读资料：在原厂命令行里执行 `cat /proc/mtd` 和 `cat /sys/devices/system/qfprom/qfprom0/authenticate`，把输出贴到 Issue 里（不含私密信息）；
- 请不要上传整片闪存备份、ART 分区或原厂固件文件。
