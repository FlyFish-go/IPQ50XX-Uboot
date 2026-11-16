---
title: Troubleshooting
description: Common problems when installing and using IPQ50XX-Uboot, arranged by symptom.
---

# Troubleshooting

Find what you see. First decide where it is stuck: during installation, a problem with the system after installation, or U-Boot itself failing to boot. The first two can almost always be solved by yourself.

## During installation

### Nothing appears on the serial console

- TX and RX may be swapped. Exchange the two wires and try again;
- Check that GND is connected and that you selected the right COM port (look in Device Manager);
- The baud rate is `115200`;
- On Xiaomi models the stock system may have disabled serial output. See the [CR8806 model page](/devices/xiaomi-cr8806#step-interrupt).

### The serial console shows only garbage

The baud rate is wrong, or the logic level is wrong (a 1.8 V router connected to a 3.3 V adapter, or the other way around). Use a multimeter to measure the voltage from router TX to GND first.

### Cannot interrupt autoboot, or can see output but cannot type

- The countdown is too short (Ruijie has only 1 s): hold Enter before powering on, and release it when you see the prompt;
- Some models need a space first, then a password (China Mobile MR3000D-CI uses `netpower`). See the model page;
- You can see output but typing does nothing: the router's RX wire is not connected properly, or the RX pin is pulled to ground by a resistor. This happens on the TCL T30 Pro: remove R5596 on version 1A, or R5600 on version 1.5A.

### TFTP keeps printing `T T T` or times out

- Is your computer's wired adapter IP `192.168.1.2`, with subnet mask `255.255.255.0`;
- In Tftpd64, is "Server interfaces" set to that address, and is the file in "Current Directory";
- Does the Windows firewall allow Tftpd64 (you can try turning the firewall off temporarily);
- Try another LAN port. Some models' stock U-Boot accepts only a specific port (see the table at the top of the model page);
- Check the file name for typos, including letter case.

### After `bootm`, it prints `Booting restricted without authentication!!` and reboots

This router has secure boot enabled and cannot have its U-Boot replaced. Stop here: power off. Nothing has been written.

### After `bootm`, it stops at `Starting kernel ...`

The device tree address is wrong. Go back to stock U-Boot and run `printenv fdtcontroladdr` again. Use the value shown on screen, with `0x` in front.

### `Wrong Image Format`

You used the wrong file. For a run from RAM you need a `-ram.uimg`; a `.mbn` is for writing to flash.

### BootBridge reports the wrong version, or 192.168.10.1 will not open

See [BootBridge web install FAQ](/install/bootbridge#frequently-asked-questions).

## After installing

### Cannot open the rescue page {#cannot-open-the-rescue-page}

- Hold the button before powering on. On H3C v0.1.0 and later, wait until the red LED has flashed three times before releasing;
- Connect the Ethernet cable to a LAN port, using only one cable at a time. Try another cable and another port;
- Set your computer's network adapter to obtain an address automatically. If you do not get one, set it manually (H3C `192.168.10.2`, other models `192.168.1.2`);
- Turn off proxy and VPN, and use an address starting with `http://`;
- Button entry has not been tested on every other model. If the button does not work, interrupt autoboot over TTL and enter `httpd`.

### The rescue page rejects my file

The rescue page refuses to write a file whose format is wrong, that is not for this router, or that is incomplete. Check the file name and SHA-256 and download it again. Do not force a file from another model.

### The firmware is flashed but the system will not boot

As long as U-Boot is intact, you can recover:

1. Open the rescue page;
2. On dual-system models, switch back to the other system (usually stock) first and confirm the router itself works;
3. Flash a different firmware, after confirming it is for the same model and the same hardware version.

### I want to go back to stock

See [Upgrade U-Boot, go back to stock](/use/upgrade#go-back-to-stock).

## U-Boot itself fails to boot

If the serial console shows no startup messages from this project's U-Boot after power-on and you cannot open the rescue page, U-Boot itself is broken.

- Do not keep powering off and trying random things, and do not try other flashing methods at random;
- If you can attach a TTL adapter: if there is still a usable copy in the stock boot chain, you may be able to interrupt autoboot. If not, you need a programming tool;
- Come to us with the information listed below.

## What to include when asking for help

- The model, the model number and hardware version on the label on the bottom of the router;
- What you did, which step you reached, and what you saw (screenshots or serial logs);
- In serial logs, first obscure MAC addresses, serial numbers and passwords;
- Do not send backup files.

Contact: QQ group 1131957442, or [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues).
