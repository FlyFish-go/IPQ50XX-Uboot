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

`tests/qemu-sim.sh` 把原厂 rootfs 复制一份当作 chroot（用户命名空间，不需要 root），stub、uhttpd 和上传 CGI
都在里面跑，用的是原厂 busybox 的 `/bin/sh`。模拟 NAND 用一台真机的分区备份拼成。覆盖：

- 上传：篡改的包、大小不对的包被拒，正确的包上传后安装程序接管端口；
- 下载：有 curl 的机型用 curl，没有 curl 的机型用 busybox wget（`ROOTFS_WGET` 给一个没有 curl 的原厂 rootfs），
  第一个地址不通时换下一个；下载到的包校验不对时不启动，改开上传页；
- 核对、备份、写入、重复写入、退出，以及各项拒绝的情况；
- 写入顺序：每次擦除都记在模拟 NAND 的 `write.log` 里，断言先整份写完备用的 APPSBL 再写正在用的那份
  （两种启动选择都测）；用 `fail.txt` 让某一份写失败，断言备用那份失败时正在用的那份没被擦过，
  正在用的那份失败后重试只写这一份。

输入都是私有文件，用环境变量给出：`ROOTFS`、`ROOTFS_WGET`（可选）、`DUMP`、`UBOOT`、`MODEL`、`ARM_CC`。
需要 binfmt_misc 的 qemu-arm 带 F 标志（chroot 里才能用）。

## 加一个机型

在 `src/profile.c` 里加一项：设备树 model、原厂固件标记、完整分区表（来自 TTL 实机调查）、备份分区、启动槽方式。只有已经用 TTL 实机验证、确认能救回来的机型才可以加。
