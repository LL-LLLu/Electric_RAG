<script setup lang="ts">
import { ref, watch } from 'vue'
import { XMarkIcon, CpuChipIcon, ChartBarIcon, ListBulletIcon, BoltIcon } from '@heroicons/vue/24/outline'
import type { EquipmentDetail } from '@/types'
import type { EquipmentGraphData } from '@/api/equipment'
import * as equipmentApi from '@/api/equipment'
import RelationshipGraph from './RelationshipGraph.vue'
import InteractiveGraph from './InteractiveGraph.vue'
import LocationsList from './LocationsList.vue'
import PowerFlowTree from './PowerFlowTree.vue'

const props = defineProps<{
  equipment: EquipmentDetail
}>()

const emit = defineEmits<{
  close: []
  navigateToEquipment: [tag: string]
}>()

// Graph state
const graphData = ref<EquipmentGraphData | null>(null)
const loadingGraph = ref(false)
const graphError = ref<string | null>(null)
const viewMode = ref<'graph' | 'list' | 'power'>('graph')

// Fetch graph data
async function loadGraphData() {
  if (!props.equipment?.tag) return

  loadingGraph.value = true
  graphError.value = null

  try {
    graphData.value = await equipmentApi.getGraph(props.equipment.tag)
  } catch (err) {
    console.error('Error loading graph data:', err)
    graphError.value = 'Failed to load graph data'
  } finally {
    loadingGraph.value = false
  }
}

// Load graph when equipment changes
watch(() => props.equipment?.tag, () => {
  loadGraphData()
}, { immediate: true })

function handleClose() {
  emit('close')
}

function handleNavigateToEquipment(tag: string) {
  emit('navigateToEquipment', tag)
}

function handleNodeClick(tag: string) {
  if (tag !== props.equipment.tag.toUpperCase()) {
    emit('navigateToEquipment', tag)
  }
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
  <div class="equipment-detail bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700">
    <!-- Header -->
    <div class="flex items-start justify-between p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 rounded-t-lg">
      <div class="flex items-start gap-3">
        <div class="p-2 bg-blue-100 rounded-lg">
          <CpuChipIcon class="h-6 w-6 text-blue-600" />
        </div>
        <div>
          <h2 class="text-xl font-bold text-gray-900 dark:text-white">
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
        class="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors"
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
          <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Description</h4>
          <p class="text-sm text-gray-600 dark:text-gray-400">{{ equipment.description }}</p>
        </div>

        <!-- Manufacturer & Model -->
        <div class="grid grid-cols-2 gap-4">
          <div v-if="equipment.manufacturer">
            <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Manufacturer</h4>
            <p class="text-sm text-gray-600 dark:text-gray-400">{{ equipment.manufacturer }}</p>
          </div>
          <div v-if="equipment.model_number">
            <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Model Number</h4>
            <p class="text-sm text-gray-600 dark:text-gray-400">{{ equipment.model_number }}</p>
          </div>
        </div>

        <!-- No additional info message -->
        <p
          v-if="!equipment.description && !equipment.manufacturer && !equipment.model_number"
          class="text-sm text-gray-500 dark:text-gray-400 italic"
        >
          No additional information available for this equipment.
        </p>
      </div>

      <!-- Divider -->
      <hr class="border-gray-200 dark:border-gray-700" />

      <!-- Relationships Section -->
      <div>
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Relationships</h3>
          <div class="flex gap-1">
            <button
              type="button"
              class="p-1.5 rounded transition-colors"
              :class="viewMode === 'graph' ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'"
              title="Graph View"
              @click="viewMode = 'graph'"
            >
              <ChartBarIcon class="h-4 w-4" />
            </button>
            <button
              type="button"
              class="p-1.5 rounded transition-colors"
              :class="viewMode === 'power' ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'"
              title="Power Flow"
              @click="viewMode = 'power'"
            >
              <BoltIcon class="h-4 w-4" />
            </button>
            <button
              type="button"
              class="p-1.5 rounded transition-colors"
              :class="viewMode === 'list' ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'"
              title="List View"
              @click="viewMode = 'list'"
            >
              <ListBulletIcon class="h-4 w-4" />
            </button>
          </div>
        </div>

        <!-- Interactive Graph View -->
        <div v-if="viewMode === 'graph'">
          <div v-if="loadingGraph" class="h-64 flex items-center justify-center bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
            <span class="text-sm text-gray-500 dark:text-gray-400">Loading graph...</span>
          </div>
          <div v-else-if="graphError" class="h-64 flex items-center justify-center bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
            <span class="text-sm text-red-600 dark:text-red-400">{{ graphError }}</span>
          </div>
          <div v-else-if="graphData && graphData.nodes.length > 1">
            <InteractiveGraph
              :nodes="graphData.nodes"
              :edges="graphData.edges"
              :center-tag="graphData.center_tag"
              @node-click="handleNodeClick"
            />
          </div>
          <div v-else class="h-32 flex items-center justify-center bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
            <span class="text-sm text-gray-500 dark:text-gray-400 italic">No connections found for this equipment.</span>
          </div>
        </div>

        <!-- Power Flow View -->
        <div v-else-if="viewMode === 'power'">
          <PowerFlowTree
            :equipment-tag="equipment.tag"
            @navigate-to-equipment="handleNavigateToEquipment"
          />
        </div>

        <!-- List View -->
        <div v-else>
          <RelationshipGraph
            :controls="equipment.controls"
            :controlled-by="equipment.controlled_by"
            @navigate-to-equipment="handleNavigateToEquipment"
          />
        </div>
      </div>

      <!-- Divider -->
      <hr class="border-gray-200 dark:border-gray-700" />

      <!-- Locations Section -->
      <LocationsList :locations="equipment.locations" />
    </div>
  </div>
</template>
