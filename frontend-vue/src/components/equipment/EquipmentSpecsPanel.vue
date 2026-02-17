<script setup lang="ts">
import { ref, watch } from 'vue'
import { TableCellsIcon } from '@heroicons/vue/24/outline'
import { getEquipmentProfile } from '@/api/supplementary'

const props = defineProps<{ tag: string }>()
const profile = ref<Record<string, unknown> | null>(null)
const loading = ref(false)

watch(() => props.tag, async (tag) => {
  loading.value = true
  profile.value = null
  try {
    const result = await getEquipmentProfile(tag)
    profile.value = JSON.parse(result.profile_json)
  } catch {
    profile.value = null
  } finally {
    loading.value = false
  }
}, { immediate: true })

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function formatKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}
</script>

<template>
  <div v-if="loading" class="py-2">
    <div class="animate-pulse flex items-center gap-2">
      <div class="h-4 w-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
      <div class="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
    </div>
  </div>

  <div v-else-if="profile && Object.keys(profile).length > 0">
    <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
      <TableCellsIcon class="h-4 w-4" />
      Specifications
    </h4>
    <dl class="grid grid-cols-2 gap-x-4 gap-y-2">
      <template v-for="(value, key) in profile" :key="key">
        <dt class="text-xs font-medium text-gray-500 dark:text-gray-400 truncate" :title="formatKey(String(key))">
          {{ formatKey(String(key)) }}
        </dt>
        <dd class="text-xs text-gray-900 dark:text-gray-100 truncate" :title="formatValue(value)">
          {{ formatValue(value) }}
        </dd>
      </template>
    </dl>
  </div>
</template>
