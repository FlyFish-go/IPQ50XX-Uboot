<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { renderText, renderInline } from '../inline'
import type { Step } from '../../devices'

const props = defineProps<{ steps: Step[]; storeKey?: string; checkable?: boolean }>()
const done = ref<boolean[]>([])
const copied = ref(-1)

function load() {
  done.value = props.steps.map(() => false)
  if (!props.storeKey) return
  try {
    const raw = localStorage.getItem('ipq50xx-steps:' + props.storeKey)
    const arr = raw ? JSON.parse(raw) : []
    done.value = props.steps.map((_, i) => !!arr[i])
  } catch {}
}
function save() {
  if (!props.storeKey) return
  try {
    localStorage.setItem('ipq50xx-steps:' + props.storeKey, JSON.stringify(done.value))
  } catch {}
}
function toggle(i: number) {
  done.value[i] = !done.value[i]
  save()
}
function reset() {
  done.value = props.steps.map(() => false)
  save()
}
async function copy(i: number, text: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = i
    setTimeout(() => (copied.value = -1), 1500)
  } catch {}
}
const count = computed(() => done.value.filter(Boolean).length)
onMounted(load)
watch(() => props.storeKey, load)
</script>

<template>
  <div class="steps">
    <div v-if="checkable" class="steps__progress">
      <div class="steps__bar"><span :style="{ width: (count / steps.length) * 100 + '%' }" /></div>
      <span class="steps__count">已完成 {{ count }} / {{ steps.length }}</span>
      <button v-if="count" class="steps__reset" type="button" @click="reset">重新开始</button>
    </div>
    <ol>
      <li v-for="(s, i) in steps" :key="i" class="step" :class="{ 'step--done': done[i] }">
        <div class="step__rail">
          <button
            v-if="checkable"
            class="step__num"
            type="button"
            :aria-pressed="done[i]"
            :title="done[i] ? '标记为未完成' : '标记为已完成'"
            @click="toggle(i)"
          >
            <svg v-if="done[i]" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" /></svg>
            <span v-else>{{ i + 1 }}</span>
          </button>
          <span v-else class="step__num"><span>{{ i + 1 }}</span></span>
        </div>
        <div class="step__body">
          <h3 class="step__title">{{ s.title }}</h3>
          <div class="step__text" v-html="renderText(s.body)" />
          <div v-if="s.cmd" class="step__cmd">
            <pre><code>{{ s.cmd.trim() }}</code></pre>
            <button type="button" @click="copy(i, s.cmd.trim())">{{ copied === i ? '已复制' : '复制' }}</button>
          </div>
          <p v-if="s.warn" class="step__warn"><strong>注意</strong><span v-html="renderInline(s.warn)" /></p>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.steps ol { list-style: none; margin: 0; padding: 0; }
.steps__progress {
  display: flex; align-items: center; gap: 12px; margin: 0 0 20px;
  font-size: 13px; color: var(--vp-c-text-2);
}
.steps__bar { flex: 1; height: 6px; border-radius: 3px; background: var(--vp-c-default-soft); overflow: hidden; }
.steps__bar span { display: block; height: 100%; background: var(--vp-c-brand-1); transition: width .3s ease; }
.steps__count { font-variant-numeric: tabular-nums; }
.steps__reset {
  font-size: 13px; color: var(--vp-c-brand-1); padding: 0 4px;
}
.steps__reset:hover { text-decoration: underline; }
.step { display: grid; grid-template-columns: 40px 1fr; gap: 14px; }
.step__rail { display: flex; flex-direction: column; align-items: center; }
.step__rail::after {
  content: ''; flex: 1; width: 2px; margin: 6px 0; border-radius: 1px;
  background: var(--vp-c-divider);
}
.step:last-child .step__rail::after { display: none; }
.step__num {
  display: grid; place-items: center; width: 34px; height: 34px; flex: none;
  border-radius: 50%; font-weight: 700; font-size: 15px;
  color: var(--vp-c-brand-1); background: var(--vp-c-brand-soft);
  border: 1.5px solid transparent; transition: background .2s, color .2s, border-color .2s;
}
button.step__num:hover { border-color: var(--vp-c-brand-1); }
.step--done .step__num { color: #fff; background: var(--vp-c-brand-1); }
.step__num svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }
.step__body { padding: 4px 0 28px; min-width: 0; }
.step__title { margin: 2px 0 6px; font-size: 17px; font-weight: 650; line-height: 28px; border: 0; padding: 0; }
.step--done .step__title { color: var(--vp-c-text-2); }
.step__text :deep(p) { margin: 6px 0; line-height: 1.75; }
.step__text :deep(ul) { margin: 6px 0; padding-left: 1.2em; }
.step__cmd { position: relative; margin: 10px 0; }
.step__cmd pre {
  margin: 0; padding: 14px 16px; overflow-x: auto; border-radius: 8px;
  background: var(--vp-code-block-bg); font-size: 13.5px; line-height: 1.6;
}
.step__cmd button {
  position: absolute; top: 8px; right: 8px; font-size: 12px; padding: 2px 10px; border-radius: 6px;
  color: var(--vp-c-text-2); background: var(--vp-c-bg); border: 1px solid var(--vp-c-divider);
}
.step__warn {
  display: flex; gap: 10px; margin: 10px 0 0; padding: 10px 14px; border-radius: 8px;
  font-size: 14px; line-height: 1.65; color: var(--warn-fg); background: var(--warn-bg);
}
.step__warn strong { flex: none; }
</style>
