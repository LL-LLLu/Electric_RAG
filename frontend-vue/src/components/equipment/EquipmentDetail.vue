<script setup lang="ts">
import { XMarkIcon, CpuChipIcon } from '@heroicons/vue/24/outline'
import type { EquipmentDetail } from '@/types'
import RelationshipGraph from './RelationshipGraph.vue'
import LocationsList from './LocationsList.vue'

const props = defineProps<{
  equipment: EquipmentDetail
}>()

const emit = defineEmits<{
  close: []
  navigateToEquipment: [tag: string]
}>()

function handleClose() {
  emit('close')
}

function handleNavigateToEquipment(tag: string) {
  emit('navigateToEquipment', tag)
}

function getTypeColor(type: string): string {
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
  <div class="equipment-detail bg-white rounded-lg shadow-lg border border-gray-200">
    <!-- Header -->
    <div class="flex items-start justify-between p-4 border-b border-gray-200 bg-gray-50 rounded-t-lg">
      <div class="flex items-start gap-3">
        <div class="p-2 bg-blue-100 rounded-lg">
          <CpuChipIcon class="h-6 w-6 text-blue-600" />
        </div>
        <div>
          <h2 class="text-xl font-bold text-gray-900">
            {{ equipment.tag }}
          </h2>
          <span
            class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium mt-1"
            :class="getTypeColor(equipment.equipment_type)"
          >
            {{ equipment.equipment_type }}
          </span>
        </div>
      </div>
      <button
        type="button"
        class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded-full transition-colors"
        @click="handleClose"
        aria-label="Close detail view"
      >
        <XMarkIcon class="h-5 w-5" />
      </button>
    </div>

    <!-- Content -->
    <div class="p-4 space-y-6 max-h-[calc(100vh-200px)] overflow-y-auto">
      <!-- Basic Info Section -->
      <div class="space-y-4">
        <!-- Description -->
        <div v-if="equipment.description">
          <h4 class="text-sm font-semibold text-gray-700 mb-1">Description</h4>
          <p class="text-sm text-gray-600">{{ equipment.description }}</p>
        </div>

        <!-- Manufacturer & Model -->
        <div class="grid grid-cols-2 gap-4">
          <div v-if="equipment.manufacturer">
            <h4 class="text-sm font-semibold text-gray-700 mb-1">Manufacturer</h4>
            <p class="text-sm text-gray-600">{{ equipment.manufacturer }}</p>
          </div>
          <div v-if="equipment.model_number">
            <h4 class="text-sm font-semibold text-gray-700 mb-1">Model Number</h4>
            <p class="text-sm text-gray-600">{{ equipment.model_number }}</p>
          </div>
        </div>

        <!-- No additional info message -->
        <p
          v-if="!equipment.description && !equipment.manufacturer && !equipment.model_number"
          class="text-sm text-gray-500 italic"
        >
          No additional information available for this equipment.
        </p>
      </div>

      <!-- Divider -->
      <hr class="border-gray-200" />

      <!-- Relationships Section -->
      <RelationshipGraph
        :controls="equipment.controls"
        :controlled-by="equipment.controlled_by"
        @navigate-to-equipment="handleNavigateToEquipment"
      />

      <!-- Divider -->
      <hr class="border-gray-200" />

      <!-- Locations Section -->
      <LocationsList :locations="equipment.locations" />
    </div>
  </div>
</template>
