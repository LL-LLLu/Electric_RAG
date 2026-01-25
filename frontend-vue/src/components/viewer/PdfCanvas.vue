<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useDragToPan } from '@/composables/useDragToPan'

const props = defineProps<{
  /** URL of the page image to display */
  imageSrc: string
  /** Zoom level as percentage (50-200) */
  zoom: number
}>()

const emit = defineEmits<{
  /** Emitted when pan position changes */
  panChange: [position: { x: number; y: number }]
  /** Emitted when image fails to load */
  imageError: []
  /** Emitted when image loads successfully */
  imageLoaded: []
}>()


// Image loading state
const imageLoading = ref(true)
const imageError = ref(false)

// Initialize drag-to-pan functionality
const { panPosition, isDragging, startDrag, onDrag, endDrag, resetPan } = useDragToPan()

// Computed transform style for the image
const imageTransform = computed(() => {
  const scale = props.zoom / 100
  return `translate(${panPosition.x}px, ${panPosition.y}px) scale(${scale})`
})

// Watch for zoom changes to emit pan position
watch(panPosition, (newPos) => {
  emit('panChange', { x: newPos.x, y: newPos.y })
}, { deep: true })

// Reset pan when image source changes
watch(() => props.imageSrc, () => {
  resetPan()
  imageLoading.value = true
  imageError.value = false
})

// Reset pan when zoom resets to 100%
watch(() => props.zoom, (newZoom, oldZoom) => {
  // Optionally reset pan when zoom resets
  if (newZoom === 100 && oldZoom !== 100) {
    // Don't auto-reset pan on zoom change - let user control it
  }
})

function handleImageLoad() {
  imageLoading.value = false
  imageError.value = false
  emit('imageLoaded')
}

function handleImageError() {
  imageLoading.value = false
  imageError.value = true
  emit('imageError')
}

// Handle Ctrl+scroll for zoom (bonus feature)
function handleWheel(event: WheelEvent) {
  if (event.ctrlKey) {
    event.preventDefault()
    // This would need to be emitted to parent for zoom control
    // For now, we just prevent the default browser zoom
  }
}

// Expose resetPan for parent component use
defineExpose({
  resetPan
})
</script>

<template>
  <div
    class="pdf-canvas relative w-full h-full overflow-hidden bg-gray-200 select-none"
    :class="{
      'cursor-grab': !isDragging,
      'cursor-grabbing': isDragging
    }"
    @mousedown="startDrag"
    @mousemove="onDrag"
    @mouseup="endDrag"
    @mouseleave="endDrag"
    @wheel="handleWheel"
  >
    <!-- Loading state -->
    <div
      v-if="imageLoading && !imageError"
      class="absolute inset-0 flex items-center justify-center"
    >
      <div class="flex flex-col items-center gap-3">
        <svg class="animate-spin h-10 w-10 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span class="text-gray-600 text-sm">Loading page...</span>
      </div>
    </div>

    <!-- Error state -->
    <div
      v-if="imageError"
      class="absolute inset-0 flex items-center justify-center"
    >
      <div class="flex flex-col items-center gap-3 text-red-500">
        <svg class="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span class="text-gray-700 text-sm">Failed to load page image</span>
      </div>
    </div>

    <!-- Image container - centered positioning -->
    <div
      class="absolute inset-0 flex items-center justify-center"
      :class="{ 'opacity-0': imageLoading && !imageError }"
    >
      <img
        :src="imageSrc"
        :style="{ transform: imageTransform, transformOrigin: 'center center' }"
        class="max-w-none pointer-events-none transition-transform duration-0"
        draggable="false"
        alt="PDF page"
        @load="handleImageLoad"
        @error="handleImageError"
      />
    </div>

    <!-- Zoom indicator overlay -->
    <div
      v-if="zoom !== 100"
      class="absolute bottom-4 right-4 bg-black/50 text-white px-2 py-1 rounded text-xs font-medium"
    >
      {{ zoom }}%
    </div>
  </div>
</template>

<style scoped>
.pdf-canvas {
  /* Smooth cursor transitions */
  transition: cursor 0.1s ease;
}

/* Disable image dragging completely */
.pdf-canvas img {
  -webkit-user-drag: none;
  user-select: none;
}
</style>
