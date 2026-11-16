---
title: "BootBridge web install (H3C)"
description: "Install U-Boot without opening the case on the H3C NX30, RT3000, RC3000, RW3000 and NX54: use the BootBridge web app to build a bridge package and upload it from the stock web admin."
---

# BootBridge web install

For H3C only: the NX30 family (NX30, RT3000, RC3000, RW3000) and the NX54, which is in testing. No need to open the case. Use only a browser and the stock web admin. Takes about 30 minutes.

## How it works

The stock upgrade page accepts only firmware in the stock format, so it cannot write U-Boot. BootBridge turns the official firmware into a bridge package: the stock system installs it as a normal upgrade, then reboots into a temporary bridge system. The bridge system identifies the board, backs up the whole flash, and checks each item. It writes U-Boot only when everything passes. The stock system stays in place.

The official firmware is processed only in your own browser. It is never uploaded to a server.

## Supported models

In the NX30 family, each model accepts only one official version. Upgrade the stock system to that version before installing. The NX54 uses the official firmware only to build the bridge package; its stock system does not need an upgrade first.

{{oem_table}}

The RT3000 has two board variants, HW-B and HW-C, which look the same. You do not need to tell them apart. BootBridge and the rescue page detect them automatically.

## Before you start

- A computer with an Ethernet port (Windows, macOS or Linux) and an Ethernet cable;
- Access to the router's stock web admin;
- Do not cut power during the process.

## Steps

The BootBridge web app divides the whole process into six steps. It shows which step you are on at the top of the page.

<figure>
<img src="/img/bootbridge-web.png" alt="Step 1 of the BootBridge web app: select a model" loading="lazy">
<figcaption>Step 1 of the BootBridge web app: select a model. The right side lists what to prepare for this run.</figcaption>
</figure>

1. Select the model: open the [BootBridge web app](/bootbridge/) on this site and select the model from the label on the bottom of the router.
2. Download the official firmware: the page gives the download address for the required version. For versions without a public link (NX30 R012, NX54), it gives a download command based on the router's SN.
3. Upgrade the system: log in to the stock web admin and upgrade to that version in the system upgrade page. Skip this if you already have it.
4. Build the bridge package: return to BootBridge, load the same official firmware, and build the bridge package.
5. Flash the bridge package: upload it in the system upgrade page of the stock web admin. The router reboots into the bridge system.
6. Install U-Boot: connect the computer to the router's LAN port with an Ethernet cable, set the network adapter to obtain an address automatically, and open `http://192.168.10.1` in a browser. Check the detection result. Build and download a backup first, then check it and install. After a successful install, reboot as the page tells you. The stock system boots as usual.

::: note Keep the backup file to yourself
The backup from step 6 holds this router's calibration data (ART), MAC address and serial number. Save it on your own computer and make a second copy. Do not post it in the group or in an Issue, and do not use it on another router.
:::

::: danger Do not upload a U-Boot file directly
Files such as `appsbl.mbn` and `appsbl.partition.bin` are not firmware the stock upgrade page accepts. Uploading them directly does nothing and may cause errors. The first install must go through BootBridge.
:::

## Check the install, v0.2.0

The new BootBridge (rule set BB2-R8) installs **U-Boot v0.2.0 release** directly. You no longer need a RAM rescue build as an intermediate step:

1. After the first boot succeeds, cut power. Hold Reset and power on. Release after the red LED has flashed three times. Open `http://192.168.10.1` in a browser to enter the rescue page (a private window is recommended; see [Enter the rescue page](/use/rescue));
2. In "System Info", check "Hardware Family": HW-A, HW-B, HW-C or HW-D;
3. Check that the version in "System Info" includes `v0.2.0`, and save a backup.

Releasing after one or two flashes switches systems. See [Flash firmware and switch systems](/use/firmware#switch-systems). Machines that were installed with pre.5 using an older tool still follow the [old upgrade steps](/use/upgrade#h3c-nx30-family).

The NX54 is under test: there is no public link for official firmware R014. The generator gives a download command based on the router's SN (as with NX30 R012). The stock system does not need upgrading first. It installs the U-Boot test build nx54-test.1. See the [NX54 model page](/devices/h3c-nx54). The BX54E is not supported yet. Holding MESH to return has not been verified on real hardware. The NX54 flash is passed using the same stock NAND table as the NX30 family (the stock table is the same as the NX30 one, with 17 flash/ECC combinations).

## Frequently asked questions

::: details BootBridge says the version is wrong or the check failed
The official firmware you downloaded is not the required version, or the file is incomplete. Download it again from the address given on the page. Do not substitute another version.
:::

::: details 192.168.10.1 does not open after uploading the bridge package
- Check that the computer has an address in `192.168.10.x` (obtained automatically). If not, set `192.168.10.2` manually with subnet mask `255.255.255.0`;
- Try another LAN port. Do not use the WAN port;
- The bridge system takes a moment to start. Wait a minute and refresh.
:::

::: details It says "APPSBL partition does not match the candidate"
The stock system was upgraded online in the web admin, so the boot partitions switched to the other set. BB2-R7 does not handle this. BB2-R8 fixes it: reopen this page, check that the rule set in the technical information is BB2-R8, build the bridge package again and flash it. You can also upload the same version of the official firmware again from the stock web page, then flash the bridge package again.
:::

::: details Detection fails, or it says the model does not match
Do not force files for a different model. Send a screenshot (hide the serial number) to the QQ group 1131957442 or to [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues).
:::

For more cases, see [Troubleshooting](/help/).
