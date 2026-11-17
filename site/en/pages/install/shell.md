---
title: In-system install (Telnet / SSH)
description: Plans and progress for installing U-Boot from the stock system without opening the case. Still being researched, not open for any model.
---

# In-system install (Telnet / SSH)

The in-system installer is still being researched and is not open for any model. [Stock SSH access on the RG-MA3063 has been tested](#ma3063-stock-shell); installing U-Boot after obtaining root still needs separate validation. To install now, use the method on the model page: [BootBridge web install](/install/bootbridge) for H3C, [TTL serial install](/install/ttl) for other models. This page explains how we plan to make this method work and how far along we are.

## What it is

No need to open the case: enable Telnet or SSH in the stock system, get a root command line, and run our installer. The installer checks the router, makes a backup, writes U-Boot and reads it back to check it. It stops if any check fails.

This will be the main install method for ordinary users in the future. TTL is reserved for the first person to verify each model and for debricking when something goes wrong.

## Why it is not open yet

- Every model has a different way to get root: some stock systems include SSH, some need community tools, some need a flaw in the stock web page, and some have no public method at all;
- The stock kernel may mark the partition holding U-Boot as read-only. In that case you cannot write it from the system. We need to check this first;
- If a write from the system fails, you cannot recover without a serial console. So someone must first walk through the process with TTL on real hardware for each model and confirm that recovery works, before we open it to ordinary users.

## What the installer checks

Before writing, every item below must match. Otherwise the installer refuses to write:

1. The model and board identifier (machid) match the model data;
2. The flash model is on the supported list;
3. The partition table names, sizes and offsets match the model data;
4. Secure boot is off: `/sys/devices/system/qfprom/qfprom0/authenticate` must be `0`;
5. The partition holding U-Boot is readable and writable.

Then it backs up the existing U-Boot partition for you to save, writes the new one, and reads it back byte by byte to check it.

## Progress by model

{{shell_table}}

## RG-MA3063: enable stock SSH { #ma3063-stock-shell }

On our RG-MA3063 hardware 1.00 unit, the factory endpoint enabled SSH in the stock system. Logging in as `admin` gave a Linux root shell.

### Enable and log in

1. Disconnect the WAN cable, connect the computer to a LAN port, and confirm that the stock web admin opens. The default address is `192.168.10.1`; use the current address if changed. This endpoint enables debug services with a public factory password. Use an isolated management network.
2. Open `http://192.168.10.1/__factory_verify_mode__` in a browser. Our unit returned:

   ```json
   {"result": "Pass"}
   ```

3. Connect from a terminal on the computer:

   ```sh
   ssh -o HostKeyAlgorithms=+ssh-rsa admin@192.168.10.1
   ```

   Verify and save the host key on the first connection. Enter the public factory password `wifi@cmcc`. The old Dropbear on our unit required the `ssh-rsa` host-key compatibility option above.
4. Run `id` after logging in. Our unit returned:

   ```text
   uid=0(root) gid=0(root)
   ```

   Although the login name is `admin`, the session has root privileges. You can then run read-only checks such as `cat /proc/mtd`. This section contains no install or partition-write commands.

### Test scope

- Recorded hardware: revision 1.00, AP-MP02.1, machid `0x8040000`. The system identifier read during this test was `wuhu-cmcc-main`; the kernel was `4.4.60`, built on 2022-01-13. The full stock firmware version was not rechecked during this test.
- Ports 22 and 23 refused connections before activation and opened after the endpoint returned success. SSH login and root privileges were confirmed. Only the Telnet port was checked; Telnet login was not tested.
- The unit already had this project's U-Boot installed while still running the Ruijie stock system. Stock U-Boot was not restored for this test. This verifies network access in the stock system, not a first install with the complete stock boot chain.
- No reboot or power cycle was performed. Persistence of SSH/Telnet after reboot is unknown. V3, V4, MA3064 and other firmware versions were not tested.
- Obtaining root does not validate in-system installation. See the [model page](/devices/ruijie-rg-ma3063) for the currently supported MA3063 install method.

Method source: [Enabling SSH on the Ruijie RG-MA3063](https://blog.kokomi.me/posts/enable-ssh-for-rg-ma3063/). The results within the scope above were reproduced on the project maintainer's unit.

## How you can help

- Tell us how to get root: how to enable Telnet or SSH in the stock system on your model. Include a source link and post it in [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues);
- Provide read-only information. Run `cat /proc/mtd` and `cat /sys/devices/system/qfprom/qfprom0/authenticate` on the stock command line, and paste the output into an Issue (without private information);
- Please do not upload a whole-flash backup, the ART partition, or stock firmware files.
