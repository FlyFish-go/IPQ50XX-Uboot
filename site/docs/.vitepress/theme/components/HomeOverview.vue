<script setup lang="ts">
import { computed } from 'vue'
import { withBase } from 'vitepress'
import { data as devices } from '../../../devices.data'
import StatusBadge from './StatusBadge.vue'

const shown = computed(() => devices.slice(0, 8))
const verified = computed(() => devices.filter((d) => d.status === 'verified').length)
const flow = [
  { t: '选机型', d: '在向导里选你的机型，只显示适用于它的步骤。' },
  { t: '进入原厂系统', d: '按机型说明打开 SSH，或用对应的网页工具，不用拆机。' },
  { t: '核对后安装', d: '安装程序先备份、再逐项核对，全部通过才写入。' },
  { t: '用救援页', d: '以后按住 Reset 通电就能进网页救援页，刷什么都行。' }
]
</script>

<template>
  <div class="ov">
    <section class="ov__sec">
      <h2 class="ov__h">四步装好</h2>
      <ol class="ov__flow">
        <li v-for="(s, i) in flow" :key="i">
          <span class="ov__n">{{ String(i + 1).padStart(2, '0') }}</span>
          <strong>{{ s.t }}</strong>
          <span>{{ s.d }}</span>
        </li>
      </ol>
    </section>

    <section class="ov__sec">
      <div class="ov__row">
        <h2 class="ov__h">支持的设备</h2>
        <a class="ov__more" :href="withBase('/devices/')">全部 {{ devices.length }} 个机型 →</a>
      </div>
      <p class="ov__lead">已验证 {{ verified }} 个，更多 IPQ50xx 机型正在收录。每个机型先由能接 TTL 的人实机验证，才对普通用户开放。</p>
      <div class="ov__devs">
        <a v-for="d in shown" :key="d.id" class="ov__dev" :href="withBase(`/devices/${d.id}`)">
          <span class="ov__vendor">{{ d.vendor }}</span>
          <span class="ov__name">{{ d.name }}</span>
          <StatusBadge :status="d.status" size="sm" />
        </a>
      </div>
    </section>

    <section class="ov__warn">
      <strong>先读这一段</strong>
      <p>改写启动程序有变砖风险。只按本站「已验证」机型的步骤操作；看到「调研中」「测试中」时，请不要在没有 TTL 或编程器的情况下尝试。</p>
    </section>
  </div>
</template>

<style scoped>
.ov { padding: 8px 0 64px; }
.ov__sec { margin-top: 56px; }
.ov__h { margin: 0 !important; padding: 0 !important; border: 0 !important; font-size: 24px; font-weight: 750; letter-spacing: -0.01em; line-height: 32px; }
.ov__row { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.ov__more { font-size: 14px; font-weight: 600; color: var(--vp-c-brand-1); text-decoration: none; white-space: nowrap; }
.ov__more:hover { text-decoration: underline; }
.ov__lead { margin: 8px 0 0 !important; color: var(--vp-c-text-2); line-height: 1.75; font-size: 15px; }
.ov__flow {
  list-style: none; margin: 20px 0 0; padding: 0;
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; counter-reset: s;
}
.ov__flow li {
  margin: 0 !important;
  position: relative; display: flex; flex-direction: column; gap: 6px; padding: 20px;
  border-radius: 14px; background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider);
  font-size: 14px; line-height: 1.7; color: var(--vp-c-text-2);
}
.ov__flow strong { font-size: 16px; color: var(--vp-c-text-1); }
.ov__n { font-size: 13px; font-weight: 800; color: var(--vp-c-brand-1); font-variant-numeric: tabular-nums; letter-spacing: .05em; }
.ov__devs { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-top: 20px; }
.ov__dev {
  display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto auto; column-gap: 8px;
  align-items: center; padding: 14px 16px; border-radius: 12px; text-decoration: none;
  border: 1px solid var(--vp-c-divider); background: var(--vp-c-bg); transition: border-color .2s, transform .2s;
}
.ov__dev:hover { border-color: var(--vp-c-brand-2); transform: translateY(-1px); }
.ov__vendor { grid-column: 1; font-size: 12px; color: var(--vp-c-text-3); }
.ov__name { grid-column: 1; font-size: 17px; font-weight: 700; color: var(--vp-c-text-1); }
.ov__dev :deep(.sb) { grid-column: 2; grid-row: 1 / 3; }
.ov__warn {
  margin-top: 56px; padding: 18px 22px; border-radius: 14px;
  background: var(--warn-bg); color: var(--warn-fg);
}
.ov__warn strong { font-size: 15px; }
.ov__warn p { margin: 6px 0 0; line-height: 1.75; font-size: 14px; }
@media (max-width: 860px) { .ov__flow { grid-template-columns: 1fr 1fr; } }
@media (max-width: 520px) { .ov__flow { grid-template-columns: 1fr; } .ov__devs { grid-template-columns: 1fr 1fr; } }
</style>
