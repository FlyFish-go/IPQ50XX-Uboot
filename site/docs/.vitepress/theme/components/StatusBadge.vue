<script setup lang="ts">
import { computed } from 'vue'
import { STATUS } from '../meta'
const props = defineProps<{ status: string; size?: 'sm' | 'md' }>()
const info = computed(() => STATUS[props.status] ?? { label: props.status, hint: '' })
</script>

<template>
  <span class="sb" :class="[`sb--${status}`, size === 'sm' && 'sb--sm']" :title="info.hint">
    <span class="sb__dot" aria-hidden="true" />{{ info.label }}
  </span>
</template>

<style scoped>
.sb {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  line-height: 22px;
  white-space: nowrap;
  color: var(--st-fg);
  background: var(--st-bg);
}
.sb--sm { font-size: 12px; padding: 0 8px; line-height: 20px; }
.sb__dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.sb--verified { --st-fg: var(--ok-fg); --st-bg: var(--ok-bg); }
.sb--community { --st-fg: var(--info-fg); --st-bg: var(--info-bg); }
.sb--testing { --st-fg: var(--warn-fg); --st-bg: var(--warn-bg); }
.sb--planned { --st-fg: var(--muted-fg); --st-bg: var(--muted-bg); }
</style>
