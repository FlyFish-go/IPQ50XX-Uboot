<script setup lang="ts">
import { ref, computed } from 'vue'
import { withBase } from 'vitepress'
import { data as devices } from '../../../devices.data'
import { MECHANISM, STATUS, STATUS_ORDER } from '../meta'
import StatusBadge from './StatusBadge.vue'

const filter = ref('all')
const counts = computed(() => {
  const c: Record<string, number> = {}
  for (const d of devices) c[d.status] = (c[d.status] ?? 0) + 1
  return c
})
const chips = computed(() => [
  { key: 'all', label: '全部', n: devices.length },
  ...STATUS_ORDER.filter((s) => counts.value[s]).map((s) => ({ key: s, label: STATUS[s].label, n: counts.value[s] }))
])
const rows = computed(() => (filter.value === 'all' ? devices : devices.filter((d) => d.status === filter.value)))
</script>

<template>
  <div class="dt">
    <div class="dt__chips" role="tablist">
      <button
        v-for="c in chips"
        :key="c.key"
        type="button"
        role="tab"
        class="chip"
        :class="{ 'chip--on': filter === c.key }"
        :aria-selected="filter === c.key"
        @click="filter = c.key"
      >
        {{ c.label }}<span class="chip__n">{{ c.n }}</span>
      </button>
    </div>
    <div class="dt__list">
      <a v-for="d in rows" :key="d.id" class="row" :href="withBase(`/devices/${d.id}`)">
        <span class="row__main">
          <span class="row__vendor">{{ d.vendor }}</span>
          <span class="row__name">{{ d.name }}</span>
          <span class="row__alias">{{ (d.aliases ?? []).join(' / ') }}</span>
        </span>
        <span class="row__cell"><span class="row__k">状态</span><StatusBadge :status="d.status" size="sm" /></span>
        <span class="row__cell"><span class="row__k">双系统</span>{{ MECHANISM[d.slots?.mechanism ?? '']?.label ?? '—' }}</span>
        <span class="row__cell"><span class="row__k">安装方式</span>{{ d.install?.label ?? '—' }}</span>
        <span class="row__go" aria-hidden="true">→</span>
      </a>
    </div>
  </div>
</template>

<style scoped>
.dt { margin-top: 20px; }
.dt__chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.chip {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px;
  font-size: 14px; border: 1px solid var(--vp-c-divider); color: var(--vp-c-text-2);
  transition: all .2s;
}
.chip:hover { color: var(--vp-c-brand-1); border-color: var(--vp-c-brand-2); }
.chip--on { color: var(--vp-c-brand-1); border-color: var(--vp-c-brand-1); background: var(--vp-c-brand-soft); font-weight: 600; }
.chip__n { font-size: 12px; opacity: .75; font-variant-numeric: tabular-nums; }
.dt__list { border: 1px solid var(--vp-c-divider); border-radius: 12px; overflow: hidden; }
.row {
  display: grid; grid-template-columns: minmax(180px, 1.4fr) 100px 1.2fr 1.2fr 20px; gap: 16px;
  align-items: center; padding: 14px 18px; color: var(--vp-c-text-1) !important; text-decoration: none !important;
  font-size: 14px; transition: background .2s;
}
.row + .row { border-top: 1px solid var(--vp-c-divider); }
.row:hover { background: var(--vp-c-bg-soft); }
.row:hover .row__go { color: var(--vp-c-brand-1); transform: translateX(2px); }
.row__main { display: flex; flex-direction: column; min-width: 0; }
.row__vendor { font-size: 12px; color: var(--vp-c-text-3); }
.row__name { font-size: 16px; font-weight: 700; }
.row__alias { font-size: 12.5px; color: var(--vp-c-text-2); }
.row__cell { color: var(--vp-c-text-2); }
.row__k { display: none; }
.row__go { color: var(--vp-c-text-3); transition: all .2s; }
@media (max-width: 760px) {
  .row { grid-template-columns: 1fr auto; gap: 6px 12px; }
  .row__main { grid-column: 1; }
  .row__cell:nth-of-type(2) { grid-column: 2; grid-row: 1; align-self: start; }
  .row__cell { grid-column: 1 / -1; font-size: 13px; }
  .row__cell:nth-of-type(2) .row__k { display: none; }
  .row__k { display: inline; margin-right: 8px; color: var(--vp-c-text-3); }
  .row__go { display: none; }
}
</style>
