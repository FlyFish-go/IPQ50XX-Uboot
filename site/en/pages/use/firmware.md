---
title: Flash firmware and switch systems
description: Flash a system firmware from the rescue page and switch between the two systems. Matching firmware for H3C and notes for other models.
---

# Flash firmware and switch systems

This project provides only U-Boot. What system you flash after installing is up to you; the rescue page writes it and switches between the two systems.

## H3C NX30 family

Two matching firmware builds are available. Flash either one from the rescue page's "Firmware Update" (a private window is recommended; see [Open the rescue page](/use/rescue)):

| Firmware | For whom | Download |
|---|---|---|
| QSDK 11.5 | You want a stable build with Qualcomm's original drivers for Wi-Fi and hardware acceleration | [H3C-RT3000-Product-R1 release page](https://github.com/FlyFish-go/H3C-RT3000-Product-R1/releases) |
| OpenWrt + NSS | You want a newer OpenWrt and its package repository while keeping NSS hardware acceleration | [H3C-Magic-NSS release page](https://github.com/FlyFish-go/H3C-Magic-NSS/releases) |

The file name includes the Hardware group, for example `HW-B`. Choose the file by the "Hardware Family" shown in the rescue page's "System Info", not by the product model: the same RT3000 may be HW-B or HW-C. Each release page says which file is used in the rescue page.

When flashing, choose which system to write to (slot 1 or slot 2). We recommend leaving the stock system in one slot and flashing third-party firmware to the other, so you can always switch back to stock.

To go back to the stock system, flash the rootfs partition you exported earlier from "Flash Backup". If you only have a `.bin` upgrade package from the H3C website, first extract the UBI from it with the [Offline firmware unpacker](/tools/fwunpack).

## Other models

This project does not provide system firmware for these models. Use the OpenWrt, ImmortalWrt and similar builds maintained by each model's community.

- The rescue page's "Firmware Update" accepts only UBI firmware. File names usually end in `.ubi` or are called factory; a rootfs partition you backed up earlier also works;
- Xiaomi CR8806: write to the other system slot, switch to it after the write, and keep the original system. Extract the UBI from the official Xiaomi `.bin` first;
- For other dual-system models, follow the hints shown on the rescue page for where to write and how to switch;
- Before flashing, confirm the firmware is for the same model and the same hardware version.

## Why only UBI {#why-only-ubi}

The rescue page's "Firmware Update" writes only a UBI system image to the system partition. It does not accept vendor upgrade packages (H3C's `.bin`, QSDK's `.img`, Xiaomi's `.bin`, etc.). The reasons:

- A vendor upgrade package contains not only the system but also boot chain files such as the stock SBL1 and U-Boot (APPSBL). The rescue page should only change the system partition, not the boot chain;
- To accept vendor packages, U-Boot would have to carry a list of "which packages are trusted". Every new vendor version would mean a U-Boot update, and U-Boot is the last thing that should be reflashed often;
- Extracting the UBI is handled by the [Offline firmware unpacker](/tools/fwunpack), entirely in your own browser. When a vendor changes format, the tool can be updated without touching U-Boot.

The rescue page does not check whether the firmware is for this router. If you flash the wrong image and the system does not boot, go back to the rescue page and flash again; U-Boot itself is not affected.

## Switch systems {#switch-systems}

### On the rescue page

The lower part of the "System Info" page lists what is installed in each system slot (see the [rescue page screenshot](/use/rescue#what-is-on-the-page)). That line is read directly from the slot: the system's own version string plus the kernel version, for example "OpenWrt 24.10.0 · Linux 6.6.73". The stock system usually appears as something like "OpenWrt Chaos Calmer 15.05.1 · Linux 4.4.60", because the vendor system is itself based on an older OpenWrt.

- H3C: you can boot a system once only (the next boot still uses the default) or set it as default;
- Other dual-system models: set the default, then reboot the router. These models do not offer "boot once";
- Single-system models show only one system.

### H3C: switch with the buttons (v0.1.0 and later)

Power off, hold Reset or Mesh/WPS while powering on, and the red LED gives one short flash per second:

| When you release | Result |
|---|---|
| Before the first flash | Boot the default system normally |
| After 1 flash | Boot slot 1 and set it as default |
| After 2 flashes | Boot slot 2 and set it as default |
| Hold through the 3rd flash | Open the rescue page at `192.168.10.1` |

- After you release, the green LED flashes once or twice quickly to show which slot was selected;
- "Slot 1" and "slot 2" count by physical position in the flash (slot 1 is at the lower address) and are unrelated to the partition names `rootfs` and `rootfs_1`;
- The Mesh/WPS button is easier to press than the small Reset hole;
- With the single-system large-partition layout: 1 flash boots the only system, 2 or 3 flashes open the rescue page.

### Upgrade from the stock system

On dual-system models, U-Boot records "which system to boot next" the same way as stock, so OpenWrt's `sysupgrade` keeps working and you do not need to return to the rescue page. See [How dual systems switch](/learn/slots).

::: danger After going back to stock, do not use the stock web admin for online upgrades
H3C stock upgrade packages include the stock SBL1 and U-Boot. When the stock system upgrades, it writes them to the other boot chain and switches to it, replacing this project's U-Boot and rescue page. To change the stock version, first extract the UBI with the [Offline firmware unpacker](/tools/fwunpack), then flash from the rescue page. On other models, if you are unsure, also avoid online upgrades from the stock system.
:::

::: note Ruijie RG-MA3063 has no automatic fallback
The stock U-Boot on the Ruijie RG-MA3063 switches to the other system automatically after several failed boots. This project's U-Boot does not copy that counter. A broken system will not fall back automatically; open the rescue page to fix it. See the [model page](/devices/ruijie-rg-ma3063#differences).
:::
