---
title: How dual systems switch
description: The common dual-system switching methods on IPQ50xx routers and how this project handles them.
---

# How dual systems switch

Many IPQ50xx routers ship with two system slots: an upgrade writes to the other slot, and if the write fails you can still boot from the original one. Different vendors record "which slot to boot next" in different ways.

## This project's principles

- If stock is dual-system, follow the stock logic. The flags U-Boot reads and writes are exactly the same as stock, so the stock firmware's own upgrade and OpenWrt's `sysupgrade` keep working.
- If stock is single-system, keep it single-system. We do not change the partition table to force in a second system that would conflict with stock firmware.
- The large partition is optional. Dual-system models can merge the two slots into one large partition to give third-party firmware more space. This is enabled only on models verified on real hardware (currently H3C).

## Common switching methods

| Method | Where it is recorded | Typical models |
|---|---|---|
| BOOTCONFIG | `0:BOOTCONFIG` / `0:BOOTCONFIG1` partitions in flash | H3C NX30 family, LYW-30M, Ruijie RG-MA3063, China Mobile (CMCC) MR3000D-CI, ELECOM, I-O DATA |
| Xiaomi environment variables | U-Boot environment variables `flag_boot_rootfs`, `flag_try_sys*_failed`, etc. | Xiaomi CR880x, AX6000, Redmi AX5400 |
| TP-Link environment variables | U-Boot environment variable `tp_boot_idx` | TP-Link Archer AX55, RE700X, Mercusys MR80X v2 |
| Linksys environment variables | U-Boot environment variable `boot_part` | Linksys MX / MR series |
| Single system | Only one system slot | GL.iNet, Zyxel, etc. |

This table comes from upstream OpenWrt device support code and our own research. Being listed here does not mean support already exists; check the status in the [Model list](/devices/). This project currently implements BOOTCONFIG and the Xiaomi environment variables.

## Where we do not match stock exactly

Following the stock logic does not mean copying every detail. Differences are listed on each model page under "Differences from stock". For example, the stock U-Boot on the Ruijie RG-MA3063 has a boot counter that switches to the other slot automatically after several failed boots; this project does not copy it.

## Why every model must first be verified over TTL

In the future, ordinary users of other models will also install from the stock system ([In-system install](/install/shell)), with no need to open the case; H3C models can already use BootBridge web install. The trade-off is that if the new U-Boot fails to boot, there is no way to recover without TTL. So before a model is opened to ordinary users, someone who can attach a TTL adapter must first go through the whole process on real hardware and confirm that recovery is possible.
