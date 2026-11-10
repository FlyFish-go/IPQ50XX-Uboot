import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import { h } from 'vue'
import HeroArt from './components/HeroArt.vue'
import DeviceWizard from './components/DeviceWizard.vue'
import DeviceTable from './components/DeviceTable.vue'
import DeviceDetail from './components/DeviceDetail.vue'
import RescueTable from './components/RescueTable.vue'
import HomeOverview from './components/HomeOverview.vue'
import StatusBadge from './components/StatusBadge.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'home-hero-image': () => h(HeroArt)
    })
  },
  enhanceApp({ app }) {
    app.component('DeviceWizard', DeviceWizard)
    app.component('DeviceTable', DeviceTable)
    app.component('DeviceDetail', DeviceDetail)
    app.component('RescueTable', RescueTable)
    app.component('HomeOverview', HomeOverview)
    app.component('StatusBadge', StatusBadge)
  }
} satisfies Theme
