<script setup lang="ts">
import { withBase } from 'vitepress'
import { data as devices } from '../../../devices.data'
const list = devices.filter((d) => d.rescue)
</script>

<template>
  <table>
    <thead><tr><th>机型</th><th>怎么进入</th><th>地址</th></tr></thead>
    <tbody>
      <tr v-for="d in list" :key="d.id">
        <td><a :href="withBase(`/devices/${d.id}`)">{{ d.vendor }} {{ d.name }}</a></td>
        <td>{{ d.rescue!.how }}</td>
        <td><code v-if="d.rescue!.address">{{ d.rescue!.address }}</code></td>
      </tr>
    </tbody>
  </table>
</template>
