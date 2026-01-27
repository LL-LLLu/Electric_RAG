<script setup lang="ts">
import { computed } from 'vue'
import {
  MagnifyingGlassPlusIcon,
  MagnifyingGlassMinusIcon,
  ArrowsPointingOutIcon
} from '@heroicons/vue/24/outline'
import type { Document } from '@/types'

const props = defineProps<{
  /** List of available documents */
  documents: Document[]
  /** Currently selected document ID */
  currentDocumentId: number | null
  /** Current zoom level (percentage) */
  zoom: number
  /** Total pages in current document */
  totalPages: number
  /** Current page number */
  currentPage: number
}>()

const emit = defineEmits<{
  /** Emitted when user selects a different document */
  selectDocument: [id: number]
  /** Emitted when zoom level changes */
  zoomChange: [level: number]
  /** Emitted when reset view is requested */
  resetView: []
}>()

// Available zoom levels
const zoomLevels = [15, 25, 50, 75, 100, 125, 150, 200]

// Check if can zoom in/out
const canZoomIn = computed(() => props.zoom < Math.max(...zoomLevels))
const canZoomOut = computed(() => props.zoom > Math.min(...zoomLevels))

function handleDocumentSelect(event: Event) {
  const target = event.target as HTMLSelectElement
  const docId = parseInt(target.value, 10)
  if (!isNaN(docId)) {
    emit('selectDocument', docId)
  }
}

function handleZoomSelect(event: Event) {
  const target = event.target as HTMLSelectElement
  const level = parseInt(target.value, 10)
  if (!isNaN(level)) {
    emit('zoomChange', level)
  }
}

function zoomIn() {
  const currentIndex = zoomLevels.indexOf(props.zoom)
  if (currentIndex >= 0 && currentIndex < zoomLevels.length - 1) {
    const nextLevel = zoomLevels[currentIndex + 1]
    if (nextLevel !== undefined) {
      emit('zoomChange', nextLevel)
    }
  } else if (currentIndex === -1) {
    // Current zoom not in list, find next higher
    const nextLevel = zoomLevels.find(l => l > props.zoom)
    if (nextLevel !== undefined) emit('zoomChange', nextLevel)
  }
}

function zoomOut() {
  const currentIndex = zoomLevels.indexOf(props.zoom)
  if (currentIndex > 0) {
    const prevLevel = zoomLevels[currentIndex - 1]
    if (prevLevel !== undefined) {
      emit('zoomChange', prevLevel)
    }
  } else if (currentIndex === -1) {
    // Current zoom not in list, find next lower
    const levels = [...zoomLevels].reverse()
    const nextLevel = levels.find(l => l < props.zoom)
    if (nextLevel !== undefined) emit('zoomChange', nextLevel)
  }
}

function resetZoom() {
  emit('zoomChange', 100)
  emit('resetView')
}
</script>

<template>
  <div class="viewer-toolbar bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-4 flex-wrap">
    <!-- Document Selector -->
    <div class="flex items-center gap-2">
      <label for="document-select" class="text-sm font-medium text-gray-700 whitespace-nowrap">
        Document:
      </label>
      <select
        id="document-select"
        :value="currentDocumentId || ''"
        class="block w-64 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-1.5"
        @change="handleDocumentSelect"
      >
        <option value="" disabled>Select a document</option>
        <option
          v-for="doc in documents"
          :key="doc.id"
          :value="doc.id"
        >
          {{ doc.original_filename || doc.filename }}
        </option>
      </select>
    </div>

    <!-- Divider -->
    <div class="h-6 w-px bg-gray-300"></div>

    <!-- Page Info -->
    <div class="text-sm text-gray-600">
      <span v-if="totalPages > 0">
        Page {{ currentPage }} of {{ totalPages }}
      </span>
      <span v-else class="text-gray-400">No document loaded</span>
    </div>

    <!-- Divider -->
    <div class="h-6 w-px bg-gray-300"></div>

    <!-- Zoom Controls -->
    <div class="flex items-center gap-2">
      <label class="text-sm font-medium text-gray-700">Zoom:</label>

      <!-- Zoom Out Button -->
      <button
        type="button"
        :disabled="!canZoomOut"
        class="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        title="Zoom out"
        @click="zoomOut"
      >
        <MagnifyingGlassMinusIcon class="h-5 w-5 text-gray-600" />
      </button>

      <!-- Zoom Level Dropdown -->
      <select
        :value="zoom"
        class="block w-20 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-1 text-center"
        @change="handleZoomSelect"
      >
        <option
          v-for="level in zoomLevels"
          :key="level"
          :value="level"
        >
          {{ level }}%
        </option>
      </select>

      <!-- Zoom In Button -->
      <button
        type="button"
        :disabled="!canZoomIn"
        class="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        title="Zoom in"
        @click="zoomIn"
      >
        <MagnifyingGlassPlusIcon class="h-5 w-5 text-gray-600" />
      </button>

      <!-- Reset View Button -->
      <button
        type="button"
        class="p-1.5 rounded-md hover:bg-gray-100 transition-colors"
        title="Reset view (100% zoom, center)"
        @click="resetZoom"
      >
        <ArrowsPointingOutIcon class="h-5 w-5 text-gray-600" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.viewer-toolbar {
  min-height: 48px;
}

/* Ensure selects have proper styling */
select {
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
  background-position: right 0.5rem center;
  background-repeat: no-repeat;
  background-size: 1.5em 1.5em;
  padding-right: 2.5rem;
  appearance: none;
}
</style>
