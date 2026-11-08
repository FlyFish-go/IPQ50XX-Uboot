import { defineLoader } from 'vitepress'
import { loadDevices, devicesDir, type Device } from './.vitepress/devices'

declare const data: Device[]
export { data }

export default defineLoader({
  watch: [devicesDir + '/*.yaml'],
  load: () => loadDevices()
})
