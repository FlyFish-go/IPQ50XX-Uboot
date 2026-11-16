---
title: About this project
description: The origin, credits, licence and disclaimer of IPQ50XX-Uboot.
---

# About this project

IPQ50XX-Uboot grew out of [H3C-NX30-Uboot](https://github.com/FlyFish-go/H3C-NX30-Uboot). That project made a U-Boot with web debricking and a dual system for the H3C NX30, RT3000, RC3000 and RW3000. We now extend it to more Qualcomm IPQ50xx routers: one configuration per model, with the same U-Boot and the same install guide.

The source is on [GitHub](https://github.com/FlyFish-go/IPQ50XX-Uboot).

## Learn more

- [How to switch systems](/learn/slots)
- [Glossary](/learn/glossary)
- [Contribute](/contribute/)

## Credits

- [chenxin527/uboot-qsdk12.5-build](https://github.com/chenxin527/uboot-qsdk12.5-build) (uBootKit) and its upstream contributors: the basis of the U-Boot and the rescue page.
- Upstream porters of [OpenWrt](https://openwrt.org/) for each model: much of the information on partition layouts, the dual system mechanism and install methods comes from their work.
- [ayu1808](https://github.com/ayu1808): the adaptation approach for the H3C project and a great deal of testing.
- Everyone in the group who helped test and gave feedback.

## Support the project

One person maintains this project in their spare time. The code and firmware are always free and public. If it helped you, you can support it on [Afdian](https://ifdian.net/a/FlyFish-go). Donations pay for new models and debugging tools (TTL, programmers, and so on). They do not guarantee adaptation work or a schedule for any model. You can also lend us a router or give us one; open an Issue to get in touch.

## Licence

U-Boot and third-party components keep their original licences and copyrights (GPL-2.0 and others). When this site refers to other tutorials, we give the source and a link only. We do not repost other people's tools or firmware.

## Disclaimer

This project is not affiliated with H3C, Xiaomi, Ruijie, China Mobile (CMCC), TCL or other router vendors. Rewriting the boot loader can brick your router. Follow the steps only for models marked "Verified", and use it at your own risk.
