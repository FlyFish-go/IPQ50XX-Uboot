<script setup lang="ts">
import { computed } from 'vue'
import { withBase } from 'vitepress'
import { data as devices } from '../../../devices.data'
import { MECHANISM, STATUS } from '../meta'
import { renderInline } from '../inline'
import StatusBadge from './StatusBadge.vue'
import StepList from './StepList.vue'

const props = defineProps<{ id: string }>()
const d = computed(() => devices.find((x) => x.id === props.id)!)
const facts = computed(() => {
  const list = [...(d.value.hardware ?? [])]
  if (d.value.soc) list.unshift({ label: '芯片', value: d.value.soc })
  return list
})
</script>

<template>
  <article v-if="d" class="dd">
    <p class="dd__eyebrow">
      <a :href="withBase('/devices/')">支持的设备</a><span>/</span>{{ d.family ?? d.vendor }}
    </p>
    <h1 class="dd__title">{{ d.vendor }} {{ d.name }}</h1>
    <div class="dd__badges">
      <StatusBadge :status="d.status" />
      <span v-if="d.slots" class="dd__tag">{{ MECHANISM[d.slots.mechanism]?.label ?? d.slots.mechanism }}</span>
      <span v-if="d.aliases?.length" class="dd__tag dd__tag--plain">{{ d.aliases.join(' / ') }}</span>
    </div>
    <p v-if="d.summary" class="dd__summary">{{ d.summary }}</p>

    <dl class="dd__facts">
      <div v-for="f in facts" :key="f.label" class="fact">
        <dt>{{ f.label }}</dt>
        <dd v-html="renderInline(f.value)" />
      </div>
      <div v-if="d.rescue" class="fact">
        <dt>进入救援页</dt>
        <dd>{{ d.rescue.how }}<template v-if="d.rescue.address">，打开 <code>{{ d.rescue.address }}</code></template></dd>
      </div>
      <div v-if="d.slot_select" class="fact">
        <dt>按键切换系统</dt>
        <dd>{{ d.slot_select }}</dd>
      </div>
    </dl>

    <p v-if="d.slots?.note" class="dd__note">{{ d.slots.note }}</p>

    <h2 id="install">安装步骤</h2>
    <div v-if="d.status === 'planned' || d.status === 'testing'" class="dd__alert">
      <strong>{{ STATUS[d.status].label }}</strong><span>{{ STATUS[d.status].hint }}。</span>
    </div>
    <p v-if="d.install?.url" class="dd__cta">
      <a class="dd__btn" :href="d.install.url" target="_blank" rel="noreferrer">打开 {{ d.install.label }} ↗</a>
    </p>
    <StepList :steps="d.steps ?? []" :store-key="d.id" :checkable="d.status !== 'planned'" />

    <template v-if="d.recovery?.length">
      <h2 id="recovery">出问题怎么办</h2>
      <ul>
        <li v-for="(r, i) in d.recovery" :key="i" v-html="renderInline(r)" />
      </ul>
    </template>

    <template v-if="d.links?.length">
      <h2 id="links">相关链接</h2>
      <ul class="dd__links">
        <li v-for="l in d.links" :key="l.url">
          <a :href="l.url" target="_blank" rel="noreferrer">{{ l.text }}</a>
        </li>
      </ul>
    </template>
  </article>
</template>

<style scoped>
.dd__eyebrow { display: flex; gap: 8px; margin: 0 0 6px; font-size: 13px; color: var(--vp-c-text-3); }
.dd__eyebrow a { color: var(--vp-c-text-2); text-decoration: none; }
.dd__eyebrow a:hover { color: var(--vp-c-brand-1); }
.dd__title { margin: 0 !important; font-size: 34px !important; line-height: 44px !important; letter-spacing: -0.02em; }
.dd__badges { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0 0; }
.dd__tag {
  display: inline-flex; align-items: center; padding: 2px 10px; border-radius: 999px;
  font-size: 13px; line-height: 22px; color: var(--vp-c-brand-1); background: var(--vp-c-brand-soft);
}
.dd__tag--plain { color: var(--vp-c-text-2); background: var(--vp-c-default-soft); }
.dd__summary { margin: 16px 0 0; font-size: 16px; line-height: 1.75; color: var(--vp-c-text-2); }
.dd__facts {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); margin: 24px 0 0;
  border: 1px solid var(--vp-c-divider); border-radius: 12px; overflow: hidden;
}
.fact {
  padding: 12px 16px; margin: 0 -1px -1px 0;
  border-right: 1px solid var(--vp-c-divider); border-bottom: 1px solid var(--vp-c-divider);
}
.fact dt { font-size: 12px; font-weight: 600; color: var(--vp-c-text-3); letter-spacing: .04em; }
.fact dd { margin: 4px 0 0; font-size: 14px; line-height: 1.65; }
.dd__note {
  margin: 16px 0 0; padding: 12px 16px; border-left: 3px solid var(--vp-c-brand-1);
  border-radius: 0 8px 8px 0; background: var(--vp-c-bg-soft); font-size: 14px; line-height: 1.7;
}
.dd__alert {
  display: flex; gap: 10px; margin: 0 0 20px; padding: 12px 16px; border-radius: 10px;
  font-size: 14px; color: var(--warn-fg); background: var(--warn-bg);
}
.dd__alert strong { flex: none; }
.dd__cta { margin: 0 0 22px; }
.dd__btn {
  display: inline-block; padding: 8px 18px; border-radius: 20px; font-weight: 600; font-size: 14px;
  color: #fff !important; background: var(--vp-c-brand-1); text-decoration: none !important;
  transition: background .2s;
}
.dd__btn:hover { background: var(--vp-c-brand-2); }
@media (max-width: 640px) {
  .dd__title { font-size: 28px !important; line-height: 36px !important; }
}
</style>
