# 系统内安装（原型）

给没有可用官方升级包的机型用：在原厂系统的 root 命令行里粘贴一行命令，然后在浏览器里完成核对、备份、写入。还没有在真机上用过，不对任何机型开放。

## 流程

1. 用户用该机型已有的方法拿到 root shell，粘贴网站给的一行命令：
   `echo '<base64>' | base64 -d | gunzip | sh`（约 3 KB，由 `mkpkg.py` 生成）。
2. 这段脚本（`stub/stub.sh.in`）先按顺序尝试从各个地址下载安装包（有 curl 用 `curl -k`，否则用 wget），
   用命令里写死的 SHA-256 核对。下载不到时，用原厂自带的 uhttpd 在 8088 端口开一个上传页，
   用户上传从 GitHub Releases 下载的安装包，同样核对 SHA-256 和大小。
3. 核对通过后启动安装包（静态 ARM 程序 `ipqi`，附带各机型的 U-Boot），接管同一个端口：
   - 核对：机型（设备树 + 原厂固件标记）、分区表、安全启动、U-Boot 分区可写、无坏块、能完整读出、BOOTCONFIG；
   - 备份：启动相关分区打成 ZIP，必须在浏览器里完整下载后才允许写入；
   - 写入：先写备用的那份 APPSBL，再写正在用的那份，每块写完读回，最后整分区读回核对。

只写 APPSBL 两份，其余分区和原厂系统都不动。程序只在 `/tmp/ipqi` 里运行。

## 构建

```bash
make ARM_CC=arm-openwrt-linux-muslgnueabi-gcc
python3 mkpkg.py --bin out/arm/ipqi --version <版本> \
  --entry uboot/cmcc-mr3000d-ci.mbn=<u-boot.mbn> --url <下载地址> --out out/pkg
```

## 测试（qemu，不碰设备）

`tests/qemu-sim.sh` 用 qemu-user 运行原厂 rootfs 里的 busybox、uhttpd 和 curl，用一台真机的分区备份拼成模拟 NAND，走完上传、下载、核对、备份、写入、重复写入、退出，以及各项拒绝的情况。输入都是私有文件，用环境变量给出：`ROOTFS`、`DUMP`、`UBOOT`、`MODEL`、`ARM_CC`。

已知的测试局限：uhttpd 执行 CGI 时用的是主机的 `/bin/sh`，不是原厂 busybox。

## 加一个机型

在 `src/profile.c` 里加一项：设备树 model、原厂固件标记、完整分区表（来自 TTL 实机调查）、备份分区、启动槽方式。只有已经用 TTL 实机验证、确认能救回来的机型才可以加。
