<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ChevronRightIcon, ChevronDownIcon, BoltIcon, ArrowUpIcon, ArrowDownIcon } from '@heroicons/vue/24/outline'
import type { PowerFlowResponse, PowerFlowNode } from '@/api/equipment'
import * as equipmentApi from '@/api/equipment'

const props = defineProps<{
  equipmentTag: string
}>()

const emit = defineEmits<{
  navigateToEquipment: [tag: string]
}>()

const powerFlow = ref<PowerFlowResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const expandedUpstream = ref(true)
const expandedDownstream = ref(true)

// Load power flow data
async function loadPowerFlow() {
  if (!props.equipmentTag) return

  loading.value = true
  error.value = null

  try {
    powerFlow.value = await equipmentApi.getPowerFlow(props.equipmentTag)
  } catch (err) {
    console.error('Error loading power flow:', err)
    error.value = 'Failed to load power flow data'
  } finally {
    loading.value = false
  }
}

watch(() => props.equipmentTag, () => {
  loadPowerFlow()
}, { immediate: true })

// Group nodes by depth for tree visualization
function groupByDepth(nodes: PowerFlowNode[]): Map<number, PowerFlowNode[]> {
  const grouped = new Map<number, PowerFlowNode[]>()
  for (const node of nodes) {
    if (!grouped.has(node.depth)) {
      grouped.set(node.depth, [])
    }
    grouped.get(node.depth)!.push(node)
  }
  return grouped
}

const upstreamByDepth = computed(() => {
  if (!powerFlow.value) return new Map()
  return groupByDepth(powerFlow.value.upstream_tree)
})

const downstreamByDepth = computed(() => {
  if (!powerFlow.value) return new Map()
  return groupByDepth(powerFlow.value.downstream_tree)
})

// Get voltage color class
function getVoltageColor(voltage: string | null): string {
  if (!voltage) return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'

  const v = voltage.toUpperCase()
  if (v.includes('480') || v.includes('460')) {
    return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
  }
  if (v.includes('277') || v.includes('240') || v.includes('208')) {
    return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300'
  }
  if (v.includes('120') || v.includes('115') || v.includes('110')) {
    return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
  }
  if (v.includes('24') || v.includes('12')) {
    return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
  }
  return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
}

function handleNodeClick(tag: string) {
  emit('navigateToEquipment', tag)
}
</script>

<template>
  <div class="power-flow-tree">
    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
      <span class="text-sm text-gray-500 dark:text-gray-400">Loading power flow...</span>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="flex items-center justify-center p-8 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
      <span class="text-sm text-red-600 dark:text-red-400">{{ error }}</span>
    </div>

    <!-- No data state -->
    <div v-else-if="!powerFlow || (powerFlow.total_upstream === 0 && powerFlow.total_downstream === 0)" class="flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
      <span class="text-sm text-gray-500 dark:text-gray-400 italic">No power flow data found for this equipment.</span>
    </div>

    <!-- Power flow data -->
    <div v-else class="space-y-4">
      <!-- Upstream Section -->
      <div v-if="powerFlow.total_upstream > 0" class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
        <button
          type="button"
          class="w-full flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors text-left"
          @click="expandedUpstream = !expandedUpstream"
        >
          <component :is="expandedUpstream ? ChevronDownIcon : ChevronRightIcon" class="h-4 w-4 text-blue-600 dark:text-blue-400" />
          <ArrowUpIcon class="h-4 w-4 text-blue-600 dark:text-blue-400" />
          <span class="text-sm font-medium text-blue-800 dark:text-blue-300">
            Upstream Power Sources
          </span>
          <span class="text-xs text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/40 px-2 py-0.5 rounded">
            {{ powerFlow.total_upstream }} {{ powerFlow.total_upstream === 1 ? 'source' : 'sources' }}
          </span>
        </button>

        <div v-if="expandedUpstream" class="border-t border-gray-200 dark:border-gray-700 p-3 space-y-2">
          <div v-for="[depth, nodes] in [...upstreamByDepth.entries()].sort((a, b) => a[0] - b[0])" :key="`upstream-${depth}`">
            <div class="text-xs text-gray-500 dark:text-gray-400 mb-1" :style="{ paddingLeft: `${(depth - 1) * 16}px` }">
              Level {{ depth }}
            </div>
            <div
              v-for="node in nodes"
              :key="node.tag"
              class="flex items-center gap-2 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
              :style="{ paddingLeft: `${(depth - 1) * 16 + 8}px` }"
              @click="handleNodeClick(node.tag)"
            >
              <BoltIcon class="h-4 w-4 text-yellow-500" />
              <span class="text-sm font-medium text-gray-900 dark:text-white">{{ node.tag }}</span>
              <span v-if="node.voltage" class="text-xs px-1.5 py-0.5 rounded" :class="getVoltageColor(node.voltage)">
                {{ node.voltage }}
              </span>
              <span v-if="node.breaker" class="text-xs text-gray-500 dark:text-gray-400">
                via {{ node.breaker }}
              </span>
              <span v-if="node.load" class="text-xs text-gray-500 dark:text-gray-400">
                ({{ node.load }})
              </span>
              <ChevronRightIcon class="h-3 w-3 text-gray-400 ml-auto" />
            </div>
          </div>
        </div>
      </div>

      <!-- Center Equipment -->
      <div class="flex items-center justify-center">
        <div class="flex items-center gap-2 px-4 py-2 bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-900 rounded-full font-medium">
          <BoltIcon class="h-5 w-5" />
          {{ equipmentTag }}
        </div>
      </div>

      <!-- Downstream Section -->
      <div v-if="powerFlow.total_downstream > 0" class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
        <button
          type="button"
          class="w-full flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/30 transition-colors text-left"
          @click="expandedDownstream = !expandedDownstream"
        >
          <component :is="expandedDownstream ? ChevronDownIcon : ChevronRightIcon" class="h-4 w-4 text-green-600 dark:text-green-400" />
          <ArrowDownIcon class="h-4 w-4 text-green-600 dark:text-green-400" />
          <span class="text-sm font-medium text-green-800 dark:text-green-300">
            Downstream Loads
          </span>
          <span class="text-xs text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/40 px-2 py-0.5 rounded">
            {{ powerFlow.total_downstream }} {{ powerFlow.total_downstream === 1 ? 'load' : 'loads' }}
          </span>
        </button>

        <div v-if="expandedDownstream" class="border-t border-gray-200 dark:border-gray-700 p-3 space-y-2">
          <div v-for="[depth, nodes] in [...downstreamByDepth.entries()].sort((a, b) => a[0] - b[0])" :key="`downstream-${depth}`">
            <div class="text-xs text-gray-500 dark:text-gray-400 mb-1" :style="{ paddingLeft: `${(depth - 1) * 16}px` }">
              Level {{ depth }}
            </div>
            <div
              v-for="node in nodes"
              :key="node.tag"
              class="flex items-center gap-2 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
              :style="{ paddingLeft: `${(depth - 1) * 16 + 8}px` }"
              @click="handleNodeClick(node.tag)"
            >
              <BoltIcon class="h-4 w-4 text-yellow-500" />
              <span class="text-sm font-medium text-gray-900 dark:text-white">{{ node.tag }}</span>
              <span v-if="node.voltage" class="text-xs px-1.5 py-0.5 rounded" :class="getVoltageColor(node.voltage)">
                {{ node.voltage }}
              </span>
              <span v-if="node.breaker" class="text-xs text-gray-500 dark:text-gray-400">
                via {{ node.breaker }}
              </span>
              <span v-if="node.load" class="text-xs text-gray-500 dark:text-gray-400">
                ({{ node.load }})
              </span>
              <ChevronRightIcon class="h-3 w-3 text-gray-400 ml-auto" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
