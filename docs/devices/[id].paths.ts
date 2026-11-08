import { loadDevices } from '../.vitepress/devices'

export default {
  paths() {
    return loadDevices().map((d) => ({
      params: { id: d.id, title: `${d.vendor} ${d.name}` }
    }))
  }
}
