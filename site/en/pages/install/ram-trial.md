---
title: "RAM trial"
description: "For testers of untested models: load U-Boot into RAM and run it once, without writing flash. Power off and everything is back to normal."
---

# RAM trial

Nobody has run this project's U-Boot on real hardware yet for "Untested" models. A RAM trial loads the U-Boot into RAM and runs it once: it never writes flash, and powering off restores the original state. A board needs a trial report before it can be marked "Verified".

<p class="caution">A successful trial does not mean you can flash it. It only gives the board its first feedback from real hardware. Do not write U-Boot to flash until a maintainer confirms the change to "Verified".</p>

## Models waiting for a trial

{{trial_list}}

Each model page has steps written for that model. You can copy the commands directly.

## What you need

- A working TTL serial connection. For wiring, logic level and computer setup, see [TTL serial install](/install/ttl);
- A computer as the TFTP server, connected to the router's LAN port with an Ethernet cable, with the computer's IP set to `192.168.1.2`;
- The trial file for your model, `<build name>-untested-ram.uimg`. The download method is in the table at the top of the model page.

## Rough steps

1. Interrupt the stock U-Boot: when you see `Hit any key to stop autoboot` after power-on, press Enter;
2. Note the device tree address: `printenv fdtcontroladdr`. If the variable is missing, look at the `fdt_blob` line in `bdinfo`. It differs by model. Do not copy someone else's address;
3. Transfer the file and boot it (replace the last line with your address). You must use `bootm` here. The stock U-Boot does not allow jumping directly to a program in RAM;
4. Check that the new U-Boot starts: the serial console shows this project's boot messages, plus a line `UNTESTED BOARD: not verified on hardware`;
5. Open the rescue page: press Enter once more during the new U-Boot countdown, enter `httpd`, and open `http://192.168.1.1` in a browser (a private window is recommended; see [Enter the rescue page](/use/rescue));
6. Power off and on again: the router boots the stock system as before.

The commands for step 3:

```
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.2
tftpboot 0x44000000 <build name>-untested-ram.uimg
bootm 0x44000000 - <address from the previous step>
```

## What to record

- Whether the serial console shows this project's boot messages, and the `UNTESTED BOARD` line;
- The flash model and the lines showing ECC detection;
- For each Ethernet port: whether plugging in a cable gives a link, whether the computer can ping `192.168.1.1`, and whether the rescue page opens (connect only one cable at a time);
- What "System Info" on the rescue page shows;
- Whether Reset and WPS / Mesh buttons do anything, and whether each LED lights up and in what colour.

::: danger Look only, do not write
Do not click buttons such as "Write" or "Update" on the rescue page. Do not run commands such as `saveenv`, `nand write` or `bootconfig set` on the serial console.
:::

## Submit a report

Whether the test succeeds or fails, please [submit a trial report](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues/new?template=board-report.yml): the model, the hardware version on the sticker on the case, the boot log, the flash model, the rescue page results, and the LEDs and buttons.

Mask the MAC address, serial number and password in the boot log. Do not upload a whole-flash backup, the ART partition, or stock firmware.
