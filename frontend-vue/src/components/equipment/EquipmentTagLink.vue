<script setup lang="ts">
import { CpuChipIcon } from '@heroicons/vue/24/outline'
import { useEquipmentQuickView } from '@/composables/useEquipmentQuickView'

const props = defineProps<{ tag: string }>()
const quickView = useEquipmentQuickView()
</script>

<template>
  <button
    type="button"
    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-800/50 transition-colors cursor-pointer"
    :title="`View details for ${tag}`"
    @click.stop="quickView.open(tag)"
  >
    <CpuChipIcon class="h-3 w-3" />
    {{ tag }}
  </button>
</template>
