export const STATUS: Record<string, { label: string; hint: string }> = {
  verified: { label: '已验证', hint: '维护者实机走通全流程' },
  community: { label: '社区验证', hint: '社区成员实机走通，维护者没有样机' },
  testing: { label: '测试中', hint: '有测试版，只建议能接 TTL 的用户尝试' },
  untested: { label: '未验证', hint: '有构建但没有在实机上验证，不建议刷入；只建议能接 TTL 的人用 RAM 试跑' },
  planned: { label: '调研中', hint: '还没有可用版本，请勿刷入' },
  research: { label: '仅收录资料', hint: '只整理了公开资料，本轮没有构建，请勿刷入' }
}

export const MECHANISM: Record<string, { label: string; short: string }> = {
  bootconfig: { label: 'BOOTCONFIG 双系统', short: 'BOOTCONFIG' },
  'xiaomi-env': { label: '小米环境变量双系统', short: '小米 env' },
  'tp-env': { label: 'TP-Link 环境变量双系统', short: 'TP-Link env' },
  'linksys-env': { label: 'Linksys 环境变量双系统', short: 'Linksys env' },
  single: { label: '单系统', short: '单系统' }
}

export const STATUS_ORDER = ['verified', 'community', 'testing', 'untested', 'planned', 'research']

export const INSTALL_SHORT: Record<string, string> = {
  bootbridge: 'BootBridge 网页',
  ssh: '原厂 SSH',
  ttl: 'TTL 串口'
}
