---
title: "TTL serial install"
description: "Install IPQ50XX-Uboot by opening the case and connecting a serial console: what to prepare, how to wire it, how to set up the computer, and why to run from RAM first."
---

# TTL serial install

All verified models except H3C ones currently require you to open the case and connect a serial console. This page covers each part behind the process: what to prepare, how to wire it, how to set up the computer, and why to run from RAM first. The exact commands for each router are on its own [model page](/devices/).

## The whole process

{{fig_flow}}

1. Wire up the serial console and get to the stock U-Boot command line;
2. Transfer the RAM build of the new U-Boot (`-ram.uimg`) with TFTP and run it from RAM. This step does not write flash;
3. Back up the whole flash from the rescue page of the new U-Boot;
4. Upload the release build (`.mbn`) and write it to flash;
5. Power off and on, and confirm the new U-Boot starts.

The first two steps only read, never write. If something goes wrong, power off and you are back where you started. Step 4 is the only one that actually writes flash. By then you already have a complete backup, and the new U-Boot has actually run on this router.

## What to prepare

| Item | Notes |
|---|---|
| USB-TTL adapter | Must output 1.8 V logic level. Many boards such as the CH340, CH343 and FT232 have a level jumper or switch. For a board with only 3.3 V, add a logic level converter |
| 3 jumper wires | If the pads have no header, you can solder thin wires, or hold a header at an angle in the vias so tension keeps it in place |
| 1 Ethernet cable | Connects the computer to the router's LAN port |
| Computer | Windows is used as the example below. On macOS or Linux, use the matching serial terminal and TFTP server |
| Serial terminal | [PuTTY](https://www.chiark.greenend.org.uk/~sgtatham/putty/) or MobaXterm |
| TFTP server | On Windows, use [Tftpd64](https://github.com/PJO2/tftpd64) |
| Files for your model | `<build name>-ram.uimg` and `<build name>.mbn`. The build name and how to download them are in the table at the top of the model page |
| Multimeter | Strongly recommended, to check GND and the logic level |

## Wiring

Connect only three wires. TX and RX cross over:

{{fig_wiring}}

Power the router from its own supply. Leave the adapter's VCC unconnected.

### How to find the serial pads

- First check the silkscreen on the board. It is usually a row of four pads or vias printed with `GND`, `TX`, `RX` and `VCC` (or `3V3`). Some boards print only a triangle or `J1`;
- GND: in continuity mode on the multimeter, the pad connected to the metal shell of the Ethernet port;
- TX: during power-on the voltage moves around 1.8 V (or 3.3 V), because boot messages are being sent out;
- RX: usually stays high and does not move at boot;
- VCC: a steady 1.8 V or 3.3 V. Do not connect it.

The pad locations, pins and logic level for each model are in the table at the top of its model page and in step 2.

### Why 1.8 V matters

Many serial pins on the IPQ50xx main chip use 1.8 V logic level. On our sample units, the Xiaomi CR8806, Ruijie RG-MA3063 and TCL T30 Pro are all 1.8 V. Connecting a 3.3 V adapter directly may at best give no text, and at worst burn out the chip's serial pins. If unsure, measure the voltage from TX to GND with a multimeter first.

## Computer setup {#computer-setup}

### Serial terminal

Install the adapter driver (CH340 / CP210x / FTDI). After plugging it in, check its COM number in "Device Manager → Ports (COM & LPT)". Set up PuTTY like this:

| Item | Value |
|---|---|
| Connection type | Serial |
| Serial line | The COM port from Device Manager, for example `COM3` |
| Speed | `115200` |
| Connection → Serial → Data bits / Stop bits / Parity | 8 / 1 / None |
| Connection → Serial → Flow control | None |

It is a good idea to turn on "All session output" in Session → Logging in PuTTY and save the log. If something goes wrong, send the log.

### IP address of the wired network adapter

Windows 11: Settings → Network & internet → Ethernet → IP assignment → Edit → Manual → turn on IPv4, then enter:

- IP address `192.168.1.2`
- Subnet mask `255.255.255.0`
- Leave gateway and DNS empty

Windows 10: Control Panel → Network and Sharing Center → Change adapter settings → right-click "Ethernet" → Properties → Internet Protocol Version 4 (TCP/IPv4).

After this, use the Ethernet cable only to connect to the router. This computer's wired network will not reach the internet for now. You can open this page on your phone to follow along.

### Tftpd64

1. Put `-ram.uimg` in a folder, for example `D:\tftp`;
2. Open Tftpd64 and select that folder under "Current Directory";
3. Select `192.168.1.2` under "Server interfaces";
4. On first run, Windows Firewall will pop up. Check "Private networks" and "Public networks" and allow it. After that, when the router downloads the file, the Tftpd64 log shows the transfer progress.

## Why run from RAM first

The stock U-Boot can load a program into RAM and run it directly. `-ram.uimg` is the RAM build of the new U-Boot: in the stock U-Boot, use `tftpboot` to load it into RAM and `bootm` to start it. It is the same code as the release build written to flash, just loaded into RAM and run from there.

This has three benefits:

- First see whether the new U-Boot runs on this machine. Continue only if the serial console, Ethernet and flash detection all work;
- Use its rescue page to make a backup. You can download the whole flash in one go, instead of copying partitions one by one in the stock system;
- Do the write from its rescue page as well. Write both APPSBL copies together, then read back and check them.

The last address in the `bootm` command is the stock U-Boot's device tree address (`fdtcontroladdr`). The new U-Boot uses it to learn about this board's hardware. It differs by model. The model page gives the value on our sample unit, but use what you see in `printenv fdtcontroladdr` on your own router.

## Secure boot

Some routers have a secure boot fuse set at the factory, so they only run boot programs signed by the vendor. You cannot replace U-Boot on those routers.

- When you run `bootm` in the stock U-Boot, if it prints `Booting restricted without authentication!!` and then reboots, secure boot is enabled. Stop here;
- If you can get a command line in the stock system, run `cat /sys/devices/system/qfprom/qfprom0/authenticate`. An output of `0` means it is not enabled.

None of our sample units have it enabled, but retail units of the same model may differ. Check every router.

## Next steps

Go back to the [Model list](/devices/), select your router, and follow its steps. Each step lists the commands to enter, what you should see, and what to do if it does not match.
