---
title: Offline firmware unpacker
description: Extract a bare UBI from a vendor package or OpenWrt firmware in your own browser, ready to flash from the rescue page. Files are not uploaded.
---

# Offline firmware unpacker

Load a firmware you downloaded yourself and extract the **UBI system image**. The file is processed only in your browser; it is not uploaded, does not go online, and does not connect to your router.

The rescue page's "Firmware Update" accepts only bare UBI. Vendor packages may also carry boot chain files such as SBL1 and U-Boot; this tool extracts only the system UBI and does not export other partitions. [Why only UBI](/use/firmware#why-only-ubi)

## Choose a firmware

{{fwunpack}}

## Which files it can handle

Files are identified by structure, not by a list of firmware versions or hashes. New versions of the same structure can be processed directly. A changed structure or a failed check gives you the reason. Hashes and CRC check file integrity; they do not verify a vendor signature or origin.

| File | How it is handled |
|---|---|
| H3C NX30 family and NX54 stock `.bin` | Skip the H3C header and extract the UBI from the system section of the FIT |
| GL.iNet GL-B3000 stock package | Handle as FIT; verified with 4.5 and 4.7 stock packaging |
| OpenWrt factory for ELECOM WRC-X3000GS2 / I-O DATA WN-DAX3000GR | Check the product header / CMOC length and CRC, then extract the UBI from FIT; stock packages from these two vendors are unverified |
| Generic QSDK FIT `.img`, `.itb` | Check the hash inside the FIT sections and extract the single UBI system section; embedded data has been verified with real packages; external data paths are implemented and pass synthetic tests but have no real sample yet |
| Xiaomi HDR1 stock package | Check the section table and whole-package CRC, then process root.ubi; verified on CR8806/8808/8809, RA81 and RD03v2; the nested FIT path is verified only synthetically |
| GecoOS IPQ50XX | Handle as FIT; some NOR packages have no UBI and the reason is shown. Vendor-modified SquashFS shows "not recognised" |
| Ruijie MA3063 stock package | Skip the Ruijie header and process the UBI in FIT; verified on wuhu and wuhu3 |
| OpenWrt sysupgrade tar | Continue unpacking if root is already UBI or FIT; for standard SquashFS, generate a UBI from kernel and root |
| Bare `.ubi` or a rootfs partition backup | Validate and output unchanged; nothing is trimmed or rewritten |

Brand names such as GL.iNet, JD Cloud and ASUS alone do not tell you whether a package contains UBI. Packages with only a separate kernel, or with NOR or eMMC file systems, cannot be converted with this tool. Other packaging formats, Xiaomi HDR2, archives and encrypted packages are unverified.

## Convert sysupgrade to UBI

The `root` in a NAND sysupgrade package is usually only SquashFS, not a UBI you can flash directly. The tool generates three dynamic volumes with a fixed configuration: `kernel`, `rootfs` and `rootfs_data`, with the last one expanding automatically. It does not preserve settings from the old system.

```text
PEB (erase block)      131072 bytes
Page / VID offset       2048 bytes
Data offset             4096 bytes
LEB (logical block)    126976 bytes
image_seq / EC              0 / 0
```

The parameters come from the NAND configuration in this project's rescue-side `firmware_rt3000_b.c`, the same as the `BLOCKSIZE=128k` and `PAGESIZE=2048` commonly used by OpenWrt qualcommax. The JS output has been compared with mtd-utils `ubinize` using the same parameters. **The same geometry does not mean the same boot method**: the target must boot from the UBI `kernel` and `rootfs` volumes. Models using a separate kernel partition, different NAND geometry or eMMC are not suitable.

## How to flash after downloading

1. Keep the original file and the extracted `.ubi`. Check the volume table, kernel information and size notes on the page.
2. [Open this project's rescue page](/use/rescue) and go to "Firmware Update".
3. Select the extracted `.ubi`, confirm the system slot and the rescue page's validation result, then write it. On dual-system models you can leave the original system in the other slot.

The model check is only a hint. The tool cannot see bad blocks on the device and cannot confirm your current partition layout. A wrongly flashed system may not boot; you can open the rescue page again and flash back the correct UBI.

::: danger Do not use the stock web admin to upgrade online
A vendor upgrade may rewrite the other SBL1 / APPSBL boot chain, and switching to it will lose this project's rescue page. To change the stock version, extract the UBI here first and flash it from the rescue page. See [Upgrade instructions](/use/firmware#upgrade-from-the-stock-system).
:::

## Save it for offline use

Save the complete built site directory and open `tools/fwunpack.html` directly. You must also keep `style.css`, `site.js`, `fwunpack/core.js` and `fwunpack/app.js`; a single HTML file is not enough. Parsing, validation, generation and download all happen on your machine.
