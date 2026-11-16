---
title: "Contribute"
description: "What to do if a model is not supported yet: the process for adding a model and ways you can help."
---

# My model is not supported yet

The goal is to cover most IPQ50xx routers, but the maintainers have only a limited number of routers, so many models need help from the community. For models already listed as "Planned" in the [Model list](/devices/#planned), that column says what is currently blocking them.

## What it takes to add a model

1. Collect information: the partition table, flash type, secure boot status, the stock dual-system method, and the serial and network ports.
2. Write the model data: one data file per model in the repository's `site/devices/` directory. This site's model pages and install steps are generated from there.
3. Produce an "Untested" build: for a RAM trial by people who can attach a TTL adapter only.
4. Verify on real hardware: someone who can attach a TTL adapter goes through the whole process. Only after the status becomes "Verified" or "Community-verified" is the model opened to ordinary users.

## How you can help

- Do a RAM trial: if you own an "Untested" model and can attach a TTL adapter, follow the [RAM trial](/install/ram-trial) and submit a report. Nothing is written to flash; power off and the original is back.
- Provide a way to get root: how to enable Telnet or SSH on your model's stock system. This is required for [In-system install](/install/shell).
- Provide read-only information: output of `cat /proc/mtd` and `cat /sys/devices/system/qfprom/qfprom0/authenticate` from the stock command line, and output of `printenv` from stock U-Boot (obscure MAC addresses, serial numbers and passwords first).
- Lend or donate a router: open an Issue to get in touch.

::: note Please do not upload
Whole-flash backups, the ART partition, or stock firmware files. They either contain private data from your router or have copyright issues. We only need the partition layout, sizes and hashes.
:::

## Where to send feedback

[GitHub Issues](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues) · [Submit a trial report](https://github.com/FlyFish-go/IPQ50XX-Uboot/issues/new?template=board-report.yml) · QQ group 1131957442
