---
title: "Open the rescue page"
description: "The web rescue page of IPQ50XX-Uboot: how to enter it on each model, how to connect your computer, and what is on the page."
---

# Open the rescue page

The rescue page is a web page built into U-Boot. It does not depend on any system installed on the router. If the system is broken or you flashed the wrong firmware, you can flash again as long as U-Boot is intact: connect an Ethernet cable to your computer and open a browser.

## How to enter on each model

{{rescue_table}}

- H3C (v0.1.0 and later): power off, hold Reset or Mesh/WPS while powering on, wait for the red LED to flash three times, then release. If you installed with an older BootBridge and are still on pre.5, hold Reset while powering on for about 3 s, then release. H3C models also enter the rescue page automatically when the system cannot boot.
- Other models: the most reliable way is to interrupt autoboot over TTL and enter `httpd`. The code also supports entering the rescue page by holding a button for a few seconds while powering on, but this has not been tested on each of these models. If the button does not work, use TTL.

## How to connect your computer

1. Connect one end of the Ethernet cable to your computer and the other to a LAN port on the router (some models require a specific port; see the model page);
2. Set your network adapter to obtain an address automatically. The rescue page runs its own DHCP server and assigns an address between `.100` and `.200`;
3. If you do not get an address, set one manually: `192.168.10.2` for H3C, `192.168.1.2` for other models, with subnet mask `255.255.255.0` in both cases;
4. Open the address for your model in a browser: `http://192.168.10.1` for H3C, `http://192.168.1.1` for other models.

**Use a private (incognito) window throughout.** The rescue page currently has a page caching issue: a regular window may show an old cached page, so the buttons or status do not match. Use a private (incognito) browser window from the moment you open the rescue page until flashing and rebooting are finished. In Chrome / Edge press `Ctrl+Shift+N`, in Firefox press `Ctrl+Shift+P`, and on a Mac replace `Ctrl` with `Cmd`. Mobile browsers also have private tabs.

Use only one Ethernet cable at a time. Turn off any proxy and VPN on your computer.

## What is on the page

<figure>
<img src="/img/rescue-overview.png" alt="The \"System Info\" page of the rescue page" loading="lazy">
<figcaption>The rescue page on an H3C NX30 (HW-D), "System Info". The upper half shows information about this router; the lower half lets you choose which system to boot.</figcaption>
</figure>

| Menu | What it is for |
|---|---|
| "System Info" | Model, Hardware group, RAM, U-Boot version; on dual-system models it also lists both systems, so you can choose which one to boot and which one to set as default |
| "System Log" | The log of this U-Boot boot; you can copy it when asking for help |
| "Firmware Update" | Upload a UBI system image: a `.ubi` firmware or a rootfs partition you backed up earlier. The format is checked first; you can confirm the write only after it passes. Stock `.bin` upgrade packages are not accepted directly; see [Why only UBI](/use/firmware#why-only-ubi) |
| "U-Boot Update" | Upload a new U-Boot image. The file is checked against this router, both APPSBL copies are written, and the data is read back for verification |
| "Flash Backup" | Download the whole flash or a single partition to your computer |
| "Web Terminal" | Run U-Boot commands in the browser, like a serial console without a cable. Use it only if you know what you are doing |

Different models show slightly different menus. Do not change advanced functions such as the partition table, MAC addresses or environment variables unless you are sure.

::: note Keep backups to yourself
The backup contains this router's calibration data (ART), MAC address and serial number. Do not post it in a group or an Issue, and do not use it to flash another router.
:::

## If you cannot open it

First try another Ethernet cable and another LAN port. Make sure you hold the button before powering on. If that does not help, see [Troubleshooting](/help/#cannot-open-the-rescue-page).

If you need to extract a system from a vendor package or sysupgrade, first use the [Offline firmware unpacker](/tools/fwunpack), then give the resulting `.ubi` to the rescue page's "Firmware Update".
