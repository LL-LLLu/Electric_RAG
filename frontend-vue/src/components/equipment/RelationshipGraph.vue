<script setup lang="ts">
import { ArrowRightIcon, ArrowLeftIcon, CpuChipIcon } from '@heroicons/vue/24/outline'
import type { Relationship } from '@/types'

defineProps<{
  controls: Relationship[]
  controlledBy: Relationship[]
}>()

const emit = defineEmits<{
  navigateToEquipment: [tag: string]
}>()

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'bg-green-100 text-green-800'
  if (confidence >= 0.6) return 'bg-yellow-100 text-yellow-800'
  return 'bg-gray-100 text-gray-600'
}

function navigateToTag(tag: string) {
  emit('navigateToEquipment', tag)
}
</script>

<template>
  <div class="relationship-graph space-y-6">
    <!-- Controls Section -->
    <div>
      <h4 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <ArrowRightIcon class="h-4 w-4 text-blue-500" />
        Controls ({{ controls.length }})
      </h4>

      <div v-if="controls.length === 0" class="text-sm text-gray-500 italic pl-6">
        This equipment does not control any other equipment.
      </div>

      <div v-else class="space-y-2">
        <button
          v-for="rel in controls"
          :key="rel.id"
          type="button"
          class="w-full text-left p-3 bg-blue-50 hover:bg-blue-100 rounded-lg border border-blue-200 transition-colors group"
          @click="navigateToTag(rel.target_tag)"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <CpuChipIcon class="h-5 w-5 text-blue-600" />
              <div>
                <span class="text-sm font-medium text-blue-900">
                  {{ rel.target_tag }}
                </span>
                <span class="ml-2 text-xs text-blue-600">
                  {{ rel.relationship_type }}
                </span>
              </div>
            </div>
            <span
              class="text-xs font-medium px-2 py-0.5 rounded"
              :class="getConfidenceColor(rel.confidence)"
            >
              {{ Math.round(rel.confidence * 100) }}%
            </span>
          </div>
        </button>
      </div>
    </div>

    <!-- Controlled By Section -->
    <div>
      <h4 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <ArrowLeftIcon class="h-4 w-4 text-purple-500" />
        Controlled By ({{ controlledBy.length }})
      </h4>

      <div v-if="controlledBy.length === 0" class="text-sm text-gray-500 italic pl-6">
        This equipment is not controlled by any other equipment.
      </div>

      <div v-else class="space-y-2">
        <button
          v-for="rel in controlledBy"
          :key="rel.id"
          type="button"
          class="w-full text-left p-3 bg-purple-50 hover:bg-purple-100 rounded-lg border border-purple-200 transition-colors group"
          @click="navigateToTag(rel.source_tag)"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <CpuChipIcon class="h-5 w-5 text-purple-600" />
              <div>
                <span class="text-sm font-medium text-purple-900">
                  {{ rel.source_tag }}
                </span>
                <span class="ml-2 text-xs text-purple-600">
                  {{ rel.relationship_type }}
                </span>
              </div>
            </div>
            <span
              class="text-xs font-medium px-2 py-0.5 rounded"
              :class="getConfidenceColor(rel.confidence)"
            >
              {{ Math.round(rel.confidence * 100) }}%
            </span>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>
