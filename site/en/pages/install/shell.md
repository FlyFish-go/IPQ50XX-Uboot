---
title: In-system install (Telnet / SSH)
description: Progress on installing U-Boot from the stock system without opening the case. RG-MA3063 has been run through on a bench unit; the installer has not been released yet.
---

# In-system install (Telnet / SSH)

The in-system installer has not been released yet and is not open for any model. On the RG-MA3063 it has been [run through from the stock state](#ma3063-bench) on one of our units. To install now, use the method on the model page: [BootBridge web install](/install/bootbridge) for H3C, [TTL serial install](/install/ttl) for other models. This page explains how this method works and how far along we are.

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

It also reads both U-Boot copies to confirm there are no bad blocks and that each reads completely, and uses BOOTCONFIG to tell which copy is in use.

Then it packs the boot-related partitions into a backup, which must be downloaded in the browser before writing is allowed. It writes the spare U-Boot copy first and the one in use second, and reads each back byte by byte.

## Progress by model

{{shell_table}}

## RG-MA3063: enable stock SSH { #ma3063-stock-shell }

On our RG-MA3063 hardware 1.00 unit, the factory endpoint enabled SSH and Telnet in the stock system. Logging in as `admin` gave a Linux root shell. **Both close again after a reboot**, so open the address in step 2 again after every reboot.

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
- Ports 22 and 23 refused connections before activation and opened after the endpoint returned success. Both SSH and Telnet accept the `admin` login, and root privileges were confirmed.
- After a power cycle, ports 22 and 23 refused connections again; opening the factory address again restored them.
- V3, V4, MA3064 and other firmware versions were not tested.

Method source: [Enabling SSH on the Ruijie RG-MA3063](https://blog.kokomi.me/posts/enable-ssh-for-rg-ma3063/). The results within the scope above were reproduced on the project maintainer's unit.

### In-system install on the bench { #ma3063-bench }

On the same unit, both U-Boot copies were first restored to the stock version (2022-01-13) and a cold boot confirmed stock U-Boot was back. Then we followed the user steps: enable SSH, paste the install command, upload the package from the browser because the router had no internet access, run the checks, download the backup, write.

- All checks passed: model, partition table (20 partitions), secure boot off, U-Boot partitions writable, no bad blocks, both copies read completely, boot selection record;
- Both U-Boot copies in the backup matched the stock version; pressing install before downloading the backup was refused;
- Both U-Boot copies read back correctly after writing. 9 cold boots followed, each one started the stock system through this U-Boot, with LAN reachable after about 65 seconds;
- The stock LuCI already uses port 8088, so the install page moved to 8089 automatically; use the address the command prints;
- The stock command line accepts at most 1023 bytes per line, so the install command spans several lines but is still one paste.

Only this one unit has been verified, and the installer has not been released yet. If a write fails, recovery needs a TTL serial console.

## How you can help

- Tell us how to get root: how to enable Telnet or SSH in the stock system on your model. Include a source link and post it in [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues);
- Provide read-only information. Run `cat /proc/mtd` and `cat /sys/devices/system/qfprom/qfprom0/authenticate` on the stock command line, and paste the output into an Issue (without private information);
- Please do not upload a whole-flash backup, the ART partition, or stock firmware files.
