---
title: In-system install (Telnet / SSH)
description: Plans and progress for installing U-Boot from the stock system without opening the case. Still being researched, not open for any model.
---

# In-system install (Telnet / SSH)

Still being researched, not open for any model. To install now, use the method on the model page: [BootBridge web install](/install/bootbridge) for H3C, [TTL serial install](/install/ttl) for other models. This page explains how we plan to make this method work and how far along we are.

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

## How you can help

- Tell us how to get root: how to enable Telnet or SSH in the stock system on your model. Include a source link and post it in [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues);
- Provide read-only information. Run `cat /proc/mtd` and `cat /sys/devices/system/qfprom/qfprom0/authenticate` on the stock command line, and paste the output into an Issue (without private information);
- Please do not upload a whole-flash backup, the ART partition, or stock firmware files.
