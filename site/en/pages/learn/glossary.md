---
title: "Glossary"
description: "Terms used throughout this site: U-Boot, the rescue page, APPSBL, BOOTCONFIG, ART, RAM trial, and more."
---

# Glossary

Terms used throughout this site, in the order you are likely to meet them.

| Term | Meaning |
|---|---|
| U-Boot | One of the first programs to run when the router powers on. It loads the system (OpenWrt, stock firmware) from flash and starts it. This is what this project replaces. |
| Rescue page | A web page built into U-Boot. It does not depend on any system installed on the router; use it to flash firmware, flash U-Boot, back up flash, and switch systems. See [Open the rescue page](/use/rescue). |
| APPSBL | The partition where U-Boot lives in flash. Qualcomm-based models usually have two copies: `APPSBL` and `APPSBL_1`. This project writes both together. |
| Dual system, system slot | Two systems in flash (for example `rootfs` and `rootfs_1`), so if one breaks the other can still boot. See [How dual systems switch](/learn/slots). |
| BOOTCONFIG | A pair of small partitions on Qualcomm platforms that record "which slot to boot next". Many models from H3C, Ruijie and China Mobile (CMCC) use it. |
| ART | The partition holding Wi-Fi calibration data and MAC addresses. It is different on every router. Do not share it, and do not write it into another router. |
| Hardware group (HW-A / B / C / D) | The H3C NX30 family is split into four groups by board. One product model can map to different groups (RT3000 comes as HW-B and HW-C), so choose files by the "Hardware Family" shown on the rescue page, not by model. |
| BootBridge, bridge package | The web install tool for H3C models. It turns official firmware into a bridge package, uses the stock upgrade function to install a temporary system, and uses that system to back up and write U-Boot. See [BootBridge web install](/install/bootbridge). |
| TTL, serial console | The interface on the board for viewing boot messages and entering commands. Connect a USB-TTL adapter to your computer; settings are usually 115200 8N1. See [TTL serial install](/install/ttl). |
| Logic level | The voltage of the serial signals. Many IPQ50xx models use 1.8 V; a 3.3 V adapter can damage the chip. |
| Stock U-Boot command line | The prompt that appears when you interrupt autoboot at power-on, for example `IPQ5018#`. RAM trials and TTL installs both start here. |
| TFTP | A simple way to transfer files. Stock U-Boot uses it to download files from a computer, which must run a TFTP server (for example Tftpd64). |
| RAM trial, `-ram.uimg` | Load the new U-Boot into RAM and run it once without writing flash; power off and the original is back. A `-ram.uimg` file is made to be run this way. See [RAM trial](/install/ram-trial). |
| `.mbn` | The release U-Boot file written to the APPSBL partition. Use it only from the rescue page's "U-Boot Update", not on the stock upgrade page. |
| Device tree address (`fdtcontroladdr`) | The memory address where stock U-Boot keeps the data describing this board's hardware. A RAM trial needs it for `bootm`; it differs between models. |
| machid, CDT | Identifiers Qualcomm platforms use to tell boards apart, stored in the CDT partition. Different hardware versions of the same product model may have different machids. |
| Secure boot | A fuse blown at the factory that allows only vendor-signed boot programs to run. A router with secure boot enabled cannot have its U-Boot replaced. |
| NAND, ECC | The type of flash used in routers and its error-correction method (4-bit, 8-bit). U-Boot must use the right ECC to read and write correctly; this project detects it automatically. |
| UBI | A common volume format on NAND. OpenWrt factory firmware is usually a `.ubi` file. |
