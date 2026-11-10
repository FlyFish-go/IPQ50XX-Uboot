#ifndef __RTL8367S_UBOOT_H__
#define __RTL8367S_UBOOT_H__
int rtl8367s_switch_init(void);
#ifdef CONFIG_H3C_RTL8367S_SGMII
int rtl8367s_sgmii_link_down(void);
int rtl8367s_sgmii_link_up(void);
#endif
#endif
