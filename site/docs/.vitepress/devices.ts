// Single source of truth: <repo>/devices/*.yaml.
// The site, and later the installer checks, both read these files.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from 'yaml'

export const devicesDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../devices'
)

export interface Step {
  title: string
  body?: string
  cmd?: string
  warn?: string
}

export interface Device {
  id: string
  order?: number
  vendor: string
  name: string
  aliases?: string[]
  soc?: string
  status: 'verified' | 'community' | 'testing' | 'planned'
  family?: string
  summary?: string
  hardware?: { label: string; value: string }[]
  slots?: { mechanism: string; note?: string }
  install?: { method: string; label: string; url?: string }
  steps?: Step[]
  rescue?: { how: string; address?: string }
  slot_select?: string
  recovery?: string[]
  links?: { text: string; url: string }[]
}

const STATUSES = ['verified', 'community', 'testing', 'planned']

export function loadDevices(): Device[] {
  const files = fs
    .readdirSync(devicesDir)
    .filter((f) => f.endsWith('.yaml'))
    .sort()
  const list = files.map((f) => {
    const d = parse(fs.readFileSync(path.join(devicesDir, f), 'utf8')) as Device
    const where = `devices/${f}`
    if (!d || typeof d !== 'object') throw new Error(`${where}: empty`)
    for (const k of ['id', 'vendor', 'name', 'status'] as const)
      if (!d[k]) throw new Error(`${where}: missing "${k}"`)
    if (d.id + '.yaml' !== f) throw new Error(`${where}: id must match file name`)
    if (!STATUSES.includes(d.status))
      throw new Error(`${where}: status must be one of ${STATUSES.join(', ')}`)
    return d
  })
  return list.sort((a, b) => (a.order ?? 999) - (b.order ?? 999) || a.id.localeCompare(b.id))
}
