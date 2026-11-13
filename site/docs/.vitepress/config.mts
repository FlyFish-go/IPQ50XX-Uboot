import { defineConfig } from 'vitepress'
import { loadDevices } from './devices'

const BASE = '/IPQ50XX-Uboot/'
const statusMark: Record<string, string> = {
  verified: '',
  community: ' · 社区',
  testing: ' · 测试中',
  untested: ' · 未验证',
  planned: ' · 调研中',
  research: ' · 资料'
}

export default defineConfig({
  lang: 'zh-CN',
  title: 'IPQ50XX-Uboot',
  description: '给 IPQ50xx 路由器装一个好用的 U-Boot：网页救砖、照原厂逻辑的双系统、写入前逐项核对。',
  base: BASE,
  cleanUrls: false,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: BASE + 'logo.svg' }],
    ['meta', { name: 'theme-color', content: '#0f766e' }]
  ],
  transformPageData(pageData) {
    const t = (pageData.params as any)?.title
    if (t) pageData.title = t
  },
  themeConfig: {
    logo: '/logo.svg',
    nav: [
      { text: '安装向导', link: '/guide/', activeMatch: '^/guide/' },
      { text: '支持的设备', link: '/devices/', activeMatch: '^/devices/' },
      { text: '原理', link: '/concepts/slots', activeMatch: '^/concepts/' },
      { text: '参与收录', link: '/contribute/', activeMatch: '^/contribute/' }
    ],
    sidebar: [
      {
        text: '开始',
        items: [
          { text: '安装向导', link: '/guide/' },
          { text: '进入救援页', link: '/guide/rescue' },
          { text: '出问题怎么办', link: '/guide/recovery' }
        ]
      },
      {
        text: '设备',
        items: [
          { text: '全部设备', link: '/devices/' },
          ...loadDevices().map((d) => ({
            text: `${d.vendor} ${d.name}${statusMark[d.status] ?? ''}`,
            link: `/devices/${d.id}`
          }))
        ]
      },
      {
        text: '原理',
        items: [{ text: '双系统怎么切换', link: '/concepts/slots' }]
      },
      {
        text: '参与',
        items: [
          { text: '参与收录', link: '/contribute/' },
          { text: '关于本项目', link: '/about' }
        ]
      }
    ],
    socialLinks: [{ icon: 'github', link: 'https://github.com/FlyFish-go/IPQ50XX-Uboot' }],
    footer: {
      message: 'U-Boot 部分遵循 GPL-2.0 · 本项目与各路由器厂商无关',
      copyright: '© 2026 FlyFish-go'
    },
    outline: { label: '本页目录' },
    docFooter: { prev: '上一页', next: '下一页' },
    darkModeSwitchLabel: '外观',
    lightModeSwitchTitle: '切换到浅色',
    darkModeSwitchTitle: '切换到深色',
    sidebarMenuLabel: '菜单',
    returnToTopLabel: '回到顶部',
    notFound: {
      title: '页面不存在',
      quote: '链接可能已经变了，从首页重新找找看。',
      linkText: '回到首页'
    },
    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索', buttonAriaLabel: '搜索' },
          modal: {
            noResultsText: '没有找到结果',
            resetButtonTitle: '清除',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' }
          }
        }
      }
    }
  }
})
