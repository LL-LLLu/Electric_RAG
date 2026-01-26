<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  type: string | null | undefined
  size?: 'sm' | 'md'
}>()

const typeConfig: Record<string, { label: string; class: string }> = {
  ONE_LINE: {
    label: 'One-Line',
    class: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
  },
  PID: {
    label: 'P&ID',
    class: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
  },
  CONTROL_SCHEMATIC: {
    label: 'Control',
    class: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300'
  },
  WIRING_DIAGRAM: {
    label: 'Wiring',
    class: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
  },
  SCHEDULE: {
    label: 'Schedule',
    class: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
  },
  GENERAL: {
    label: 'General',
    class: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
  }
}

const config = computed(() => {
  const t = props.type?.toUpperCase() || 'GENERAL'
  return typeConfig[t] || typeConfig.GENERAL
})

const sizeClass = computed(() => {
  return props.size === 'md' ? 'px-2.5 py-1 text-xs' : 'px-2 py-0.5 text-xs'
})
</script>

<template>
  <span
    v-if="type"
    class="inline-flex items-center rounded-full font-medium"
    :class="[config.class, sizeClass]"
  >
    {{ config.label }}
  </span>
</template>
