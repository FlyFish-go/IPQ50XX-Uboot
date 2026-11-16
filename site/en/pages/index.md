---
title: IPQ50XX-Uboot
full_title: "IPQ50XX-Uboot: a U-Boot with a web rescue page for IPQ50xx routers"
description: Install a U-Boot with a web rescue page on Qualcomm IPQ50xx routers. The stock dual system keeps working. Model list, install steps and debricking.
---

# Replace the U-Boot on IPQ50xx routers with a web rescue page

After installation, if you flash a broken system you can go to the rescue page and flash again, without opening the case or using a programmer. The stock dual system keeps working.
{: .lead}

{{home_finder}}

Each model has its own page with every command to enter on that router, what should appear on screen, and what to do if it does not.

## Models you can install now

{{verified_table}}

Click a model name for its install steps.

## Other models

These models cannot be installed by following the steps yet. See the [Model list](/devices/) for the full list with filters.

{{home_others}}

## What the install changes

U-Boot is one of the first programs to run when the router powers on. It decides which system to boot. The flash usually holds two copies (`APPSBL` and `APPSBL_1`). The install replaces those two copies and leaves the other partitions alone.

{{fig_flash}}

- Back up the whole flash before writing. The backup holds this router's calibration data, MAC address and serial number. Keep it to yourself.
- Write both copies together, read them back and check them. Report an error if they do not match.
- To go back to stock, write those two partitions back from the backup. See [Upgrade U-Boot, go back to stock](/use/upgrade).

This project only handles U-Boot. For the system firmware, use the community-maintained OpenWrt builds for each model. The H3C NX30 family has its own matching QSDK and OpenWrt firmware. See [Flash firmware and switch systems](/use/firmware).

## Which method to use

The model decides which method to use. The model page only lists the one that applies to it.

| Method | Models | Open the case? |
|---|---|---|
| [BootBridge web install](/install/bootbridge) | H3C NX30, RT3000, RC3000, RW3000, NX54 (testing) | No |
| [TTL serial install](/install/ttl) | Other verified models | Yes |
| [RAM trial](/install/ram-trial) | Untested models, for testers only | Yes, no flash write |

[In-system install](/install/shell) (Telnet / SSH), which does not need the case opened, is still being researched.

## What it looks like after installation

<figure>
<img src="/img/rescue-overview.png" alt="The System Info page of the rescue page" loading="lazy">
<figcaption>The rescue page on an H3C NX30. Connect the computer with an Ethernet cable, open a browser, and it works without any system installed on the router.</figcaption>
</figure>

- [Enter the rescue page](/use/rescue): how each model enters it and how to connect the computer.
- [Flash firmware and switch systems](/use/firmware): flash third-party firmware and switch between the two systems.
- [Upgrade U-Boot, go back to stock](/use/upgrade)

## If something goes wrong

Check by symptom first: [Troubleshooting](/help/). If that does not help, ask in the QQ group 1131957442 or in [GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues). If your model is not listed, see [Contribute](/contribute/).
