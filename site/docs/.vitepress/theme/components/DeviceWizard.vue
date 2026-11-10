<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { withBase } from 'vitepress'
import { data as devices } from '../../../devices.data'
import { MECHANISM, STATUS, INSTALL_SHORT } from '../meta'
import StatusBadge from './StatusBadge.vue'
import StepList from './StepList.vue'

const selected = ref<string | null>(null)
const stepsEl = ref<HTMLElement | null>(null)
const device = computed(() => devices.find((d) => d.id === selected.value) ?? null)

const groups = computed(() => {
  const map = new Map<string, typeof devices>()
  for (const d of devices) {
    const key = d.vendor
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(d)
  }
  return [...map.entries()]
})

function choose(id: string) {
  selected.value = id
  try {
    const u = new URL(location.href)
    u.searchParams.set('d', id)
    history.replaceState(null, '', u)
  } catch {}
  nextTick(() => stepsEl.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}
function clear() {
  selected.value = null
  try {
    const u = new URL(location.href)
    u.searchParams.delete('d')
    history.replaceState(null, '', u)
  } catch {}
}
onMounted(() => {
  const id = new URLSearchParams(location.search).get('d')
  if (id && devices.some((d) => d.id === id)) selected.value = id
})
</script>

<template>
  <div class="wiz">
    <section class="wiz__pick" :class="{ 'wiz__pick--compact': device }">
      <header class="wiz__head">
        <span class="wiz__no">1</span>
        <div>
          <h2 class="wiz__h">选择你的机型</h2>
          <p class="wiz__sub">看机身底部铭牌上的型号。同一型号可能有不同主板，安装时会自动识别。</p>
        </div>
      </header>
      <div v-for="[vendor, list] in groups" :key="vendor" class="wiz__group">
        <div class="wiz__vendor">{{ vendor }}</div>
        <div class="wiz__grid">
          <button
            v-for="d in list"
            :key="d.id"
            type="button"
            class="card"
            :class="{ 'card--on': selected === d.id, 'card--planned': d.status === 'planned' }"
            :aria-pressed="selected === d.id"
            @click="choose(d.id)"
          >
            <span class="card__top">
              <span class="card__name">{{ d.name }}</span>
              <StatusBadge :status="d.status" size="sm" />
            </span>
            <span class="card__alias">{{ (d.aliases ?? []).join(' / ') }}</span>
            <span class="card__meta">
              {{ MECHANISM[d.slots?.mechanism ?? '']?.short ?? '—' }} · {{ INSTALL_SHORT[d.install?.method ?? ''] ?? '—' }}
            </span>
          </button>
        </div>
      </div>
      <p class="wiz__missing">
        没有你的机型？<a :href="withBase('/contribute/')">看看怎么参与收录</a>
      </p>
    </section>

    <section v-if="device" ref="stepsEl" class="wiz__run">
      <header class="wiz__head">
        <span class="wiz__no">2</span>
        <div class="wiz__runhead">
          <div>
            <h2 class="wiz__h">{{ device.vendor }} {{ device.name }}：跟着做</h2>
            <p class="wiz__sub">
              {{ device.summary }}
              <a :href="withBase(`/devices/${device.id}`)">机型详情</a>
            </p>
          </div>
          <button type="button" class="wiz__change" @click="clear">换一个机型</button>
        </div>
      </header>
      <div v-if="device.status === 'planned' || device.status === 'testing'" class="wiz__alert">
        <strong>{{ STATUS[device.status].label }}</strong>
        <span>{{ STATUS[device.status].hint }}。下面的步骤只用来说明计划，不要照着刷。</span>
      </div>
      <StepList
        :steps="device.steps ?? []"
        :store-key="device.id"
        :checkable="device.status !== 'planned'"
      />
    </section>
  </div>
</template>

<style scoped>
.wiz { margin-top: 24px; }
.wiz__head { display: flex; gap: 14px; align-items: flex-start; margin-bottom: 18px; }
.wiz__no {
  flex: none; display: grid; place-items: center; width: 30px; height: 30px; margin-top: 2px;
  border-radius: 9px; font-weight: 700; color: #fff; background: var(--vp-c-brand-1);
}
.wiz__h { margin: 0; padding: 0; border: 0; font-size: 20px; line-height: 32px; letter-spacing: -0.01em; }
.wiz__sub { margin: 2px 0 0; color: var(--vp-c-text-2); font-size: 14px; line-height: 1.7; }
.wiz__sub a { margin-left: 4px; }
.wiz__group + .wiz__group { margin-top: 18px; }
.wiz__vendor {
  margin: 0 0 8px; font-size: 12px; font-weight: 700; letter-spacing: .08em;
  color: var(--vp-c-text-3); text-transform: uppercase;
}
.wiz__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; }
.card {
  display: flex; flex-direction: column; gap: 4px; padding: 14px 16px; text-align: left;
  border-radius: 12px; border: 1.5px solid var(--vp-c-divider); background: var(--vp-c-bg-soft);
  transition: border-color .2s, background .2s, transform .2s, box-shadow .2s;
}
.card:hover { border-color: var(--vp-c-brand-2); transform: translateY(-1px); }
.card:focus-visible { outline: 2px solid var(--vp-c-brand-1); outline-offset: 2px; }
.card--on {
  border-color: var(--vp-c-brand-1); background: var(--vp-c-brand-soft);
  box-shadow: 0 0 0 3px var(--vp-c-brand-soft);
}
.card--planned .card__name { color: var(--vp-c-text-2); }
.card__top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.card__name { font-size: 17px; font-weight: 700; color: var(--vp-c-text-1); }
.card__alias { font-size: 13px; color: var(--vp-c-text-2); min-height: 20px; }
.card__meta { font-size: 12px; color: var(--vp-c-text-3); }
.wiz__missing { margin: 16px 0 0; font-size: 14px; color: var(--vp-c-text-2); }
.wiz__run {
  margin-top: 36px; padding-top: 28px; border-top: 1px solid var(--vp-c-divider);
  scroll-margin-top: calc(var(--vp-nav-height) + 16px);
}
.wiz__runhead { flex: 1; display: flex; gap: 12px; justify-content: space-between; align-items: flex-start; }
.wiz__change {
  flex: none; font-size: 13px; padding: 4px 12px; border-radius: 8px;
  border: 1px solid var(--vp-c-divider); color: var(--vp-c-text-2);
}
.wiz__change:hover { color: var(--vp-c-brand-1); border-color: var(--vp-c-brand-1); }
.wiz__alert {
  display: flex; gap: 10px; margin: 0 0 22px; padding: 12px 16px; border-radius: 10px;
  font-size: 14px; line-height: 1.65; color: var(--warn-fg); background: var(--warn-bg);
}
.wiz__alert strong { flex: none; }
@media (max-width: 640px) {
  .wiz__grid { grid-template-columns: 1fr 1fr; gap: 10px; }
  .card { padding: 12px; }
  .card__name { font-size: 16px; }
  .card__top { flex-direction: column; align-items: flex-start; gap: 4px; }
  .wiz__runhead { flex-direction: column; }
}
</style>
