---
title: Upgrade U-Boot, go back to stock
description: Upgrade IPQ50XX-Uboot from the rescue page, and how to go back to the stock system or stock U-Boot.
---

# Upgrade U-Boot, go back to stock

## Upgrade U-Boot

On a router that already has this project's U-Boot, all upgrades are done from the rescue page's "U-Boot Update": upload the new file, write both APPSBL copies, read the data back for verification, then power off and reboot and check the version number.

### H3C NX30 family

From v0.2.0 on, there is one U-Boot file per Hardware group. U-Boot detects the flash type at boot, so you no longer need to pick a folder by flash type.

First open the rescue page. Check "Hardware Family" (HW-A, B, C, D) in "System Info", then download the two files for that group from the [v0.2.0 release page](https://github.com/FlyFish-go/IPQ50XX-Uboot/releases/tag/v0.2.0): `h3c-hw-x.mbn` and `h3c-hw-x-ram-rescue.elf` (replace x with a, b, c, d).

**Already on v0.2.0 or later**: upload `h3c-hw-x.mbn` in "U-Boot Update", wait for the write to finish, then power off and reboot.

**Still on v0.1.0, pre.5 installed by an older BootBridge, or an earlier version**: the old "U-Boot Update" accepts only the old files grouped by flash type and will reject the new ones. Use the RAM rescue build as an intermediate step. The new BootBridge on this site installs v0.2.0 directly, so this step is not needed:

1. Open "Web Terminal", click "Upload file", and select `h3c-hw-x-ram-rescue.elf`;
2. After the upload finishes, enter `bootelf ${fileaddr}` in the command box and press Enter. The page will disconnect; this is normal;
3. Wait about 10 s, then open `http://192.168.10.1` again (a private window is recommended; see [Open the rescue page](/use/rescue)). "System Info" should say "RAM rescue build (not installed in flash)". Nothing has been written yet;
4. In "U-Boot Update" on this new page, upload `h3c-hw-x.mbn`. Both APPSBL copies are written and read back for verification;
5. Power off and reboot. The version in "System Info" includes `v0.2.0`.

If the page still will not open after step 2, power off and reboot to return to the original version; nothing has changed. Just try again.

### Other models

Get the new `<build name>.mbn` from the Download column of the table at the top of the model page and upload it in the rescue page's "U-Boot Update". Use only the file for your model. If the page rejects it, do not force a file from another model.

## Go back to stock

First decide what you want to go back to.

### You only want to use the stock system

On dual-system models, the stock system stays in one of the slots. Just switch to it from the rescue page or with the buttons; U-Boot does not need to change. But on H3C models, do not use online upgrade in the stock web admin: it replaces this project's U-Boot. See [Upgrade from the stock system](/use/firmware#upgrade-from-the-stock-system).

### You also want to restore the stock U-Boot

This means writing back the stock U-Boot partition you backed up before installation:

- H3C: use the backup saved when installing with BootBridge;
- Other models: use the whole-flash backup downloaded from the rescue page before installation.

An error when writing the boot partitions can brick the router, and the partition locations differ between models. First explain your situation in the QQ group 1131957442 or in [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues), confirm the steps, and only then proceed. Ideally have a TTL adapter on hand.

::: note A backup can only be used on the router it came from
The backup contains this router's calibration data (ART), MAC address and serial number. Writing in someone else's backup, or one from another of your own routers, will give you the wrong Wi-Fi calibration and MAC address.
:::

If you need to extract a system from a vendor package or sysupgrade, first use the [Offline firmware unpacker](/tools/fwunpack), then give the resulting `.ubi` to the rescue page's "Firmware Update".
