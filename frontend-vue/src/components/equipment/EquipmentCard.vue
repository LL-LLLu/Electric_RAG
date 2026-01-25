<script setup lang="ts">
import { CpuChipIcon, ChevronRightIcon } from '@heroicons/vue/24/outline'
import type { Equipment } from '@/types'

const props = defineProps<{
  equipment: Equipment
}>()

const emit = defineEmits<{
  select: [equipment: Equipment]
}>()

function handleClick() {
  emit('select', props.equipment)
}

function getTypeColor(type: string): string {
  // Different colors for different equipment types
  const typeColors: Record<string, string> = {
    VFD: 'bg-blue-100 text-blue-800',
    Motor: 'bg-green-100 text-green-800',
    Pump: 'bg-cyan-100 text-cyan-800',
    Valve: 'bg-orange-100 text-orange-800',
    Sensor: 'bg-purple-100 text-purple-800',
    PLC: 'bg-red-100 text-red-800',
    Breaker: 'bg-yellow-100 text-yellow-800',
    Transformer: 'bg-indigo-100 text-indigo-800',
  }
  return typeColors[type] || 'bg-gray-100 text-gray-800'
}
</script>

<template>
  <div
    class="equipment-card bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md hover:border-blue-300 transition-all cursor-pointer"
    @click="handleClick"
  >
    <div class="p-4">
      <!-- Header with Tag and Type -->
      <div class="flex items-start justify-between mb-3">
        <div class="flex items-center gap-2">
          <CpuChipIcon class="h-5 w-5 text-blue-600 flex-shrink-0" />
          <span class="text-lg font-semibold text-gray-900">
            {{ equipment.tag }}
          </span>
        </div>
        <ChevronRightIcon class="h-5 w-5 text-gray-400" />
      </div>

      <!-- Equipment Type Badge -->
      <div class="mb-3">
        <span
          class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
          :class="getTypeColor(equipment.equipment_type)"
        >
          {{ equipment.equipment_type }}
        </span>
      </div>

      <!-- Description -->
      <p
        v-if="equipment.description"
        class="text-sm text-gray-600 line-clamp-2"
      >
        {{ equipment.description }}
      </p>
      <p v-else class="text-sm text-gray-400 italic">
        No description available
      </p>

      <!-- Additional Info -->
      <div v-if="equipment.manufacturer || equipment.model_number" class="mt-3 pt-3 border-t border-gray-100">
        <div class="flex flex-wrap gap-3 text-xs text-gray-500">
          <span v-if="equipment.manufacturer">
            <span class="font-medium">Mfr:</span> {{ equipment.manufacturer }}
          </span>
          <span v-if="equipment.model_number">
            <span class="font-medium">Model:</span> {{ equipment.model_number }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
