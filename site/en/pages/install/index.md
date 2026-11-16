---
title: Install
description: The install methods for IPQ50XX-Uboot and which models each method applies to.
---

# Install

The model decides which method to use. You do not choose. The model page only lists the method that applies to it.

| Method | Models | Open the case? |
|---|---|---|
| [BootBridge web install](/install/bootbridge) | H3C NX30, RT3000, RC3000, RW3000, NX54 (testing) | No |
| [TTL serial install](/install/ttl) | Other verified models | Yes |
| [RAM trial](/install/ram-trial) | Untested models, for testers only | Yes, and no flash write |
| [In-system install (Telnet / SSH)](/install/shell) | Being researched, not open for any model yet | No |

The methods that write flash have two things in common:

- Back up the whole flash before writing. The backup holds this router's calibration data, MAC address and serial number. Keep it to yourself.
- Write both U-Boot copies (`APPSBL` and `APPSBL_1`) together, read them back and check them. Report an error if they do not match.

First find your router in the [Model list](/devices/).

To extract the system from a vendor package or sysupgrade, first use the [Offline firmware unpacker](/tools/fwunpack). Then pass the resulting `.ubi` to "Firmware Update" on the rescue page.
