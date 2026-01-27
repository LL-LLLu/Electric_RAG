<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import * as documentsApi from '@/api/documents'
import type { Document, DocumentDetail } from '@/types'
import PdfCanvas from './PdfCanvas.vue'
import ViewerToolbar from './ViewerToolbar.vue'
import PageNavigator from './PageNavigator.vue'

const props = defineProps<{
  /** Initial document ID to load */
  documentId: number | null
  /** Initial page number (1-indexed) */
  pageNumber?: number
  /** List of available documents for the dropdown */
  documents: Document[]
}>()

const emit = defineEmits<{
  /** Emitted when document changes */
  documentChange: [id: number]
  /** Emitted when page changes */
  pageChange: [pageNumber: number]
  /** Emitted when viewer encounters an error */
  error: [message: string]
}>()

// State
const currentDocumentId = ref<number | null>(props.documentId)
const currentDocument = ref<DocumentDetail | null>(null)
const currentPage = ref(props.pageNumber || 1)
const zoom = ref(100)
const loading = ref(false)
const error = ref<string | null>(null)

// Canvas reference for resetting pan
const canvasRef = ref<InstanceType<typeof PdfCanvas> | null>(null)

// Computed
const totalPages = computed(() => currentDocument.value?.page_count || 0)

const imageUrl = computed(() => {
  if (!currentDocumentId.value || currentPage.value < 1) return ''
  return documentsApi.getPageImageUrl(currentDocumentId.value, currentPage.value)
})

// Load document details when document ID changes
async function loadDocument(docId: number) {
  if (!docId) return

  loading.value = true
  error.value = null

  try {
    currentDocument.value = await documentsApi.get(docId)
    currentDocumentId.value = docId

    // Validate current page
    if (currentPage.value > currentDocument.value.page_count) {
      currentPage.value = 1
    }
  } catch (err) {
    console.error('Failed to load document:', err)
    error.value = 'Failed to load document details'
    currentDocument.value = null
    emit('error', error.value)
  } finally {
    loading.value = false
  }
}

// Watch for prop changes
watch(() => props.documentId, (newId) => {
  if (newId && newId !== currentDocumentId.value) {
    currentDocumentId.value = newId
    currentPage.value = props.pageNumber || 1
    loadDocument(newId)
  }
})

watch(() => props.pageNumber, (newPage) => {
  if (newPage && newPage !== currentPage.value) {
    currentPage.value = newPage
  }
})

// Event handlers
function handleDocumentSelect(docId: number) {
  if (docId !== currentDocumentId.value) {
    currentPage.value = 1
    zoom.value = 100
    loadDocument(docId)
    emit('documentChange', docId)
  }
}

function handlePageChange(pageNum: number) {
  if (pageNum >= 1 && pageNum <= totalPages.value && pageNum !== currentPage.value) {
    currentPage.value = pageNum
    // Reset pan when changing pages
    canvasRef.value?.resetPan()
    emit('pageChange', pageNum)
  }
}

function handleZoomChange(level: number) {
  zoom.value = level
}

function handleResetView() {
  zoom.value = 100
  canvasRef.value?.resetPan()
}

function handlePanChange(_position: { x: number; y: number }) {
  // Could be used to sync pan position with a store or URL
  // console.log('Pan position:', _position)
}

function handleImageError() {
  error.value = 'Failed to load page image'
}

function handleImageLoaded() {
  error.value = null
}

// Keyboard navigation
function handleKeydown(event: KeyboardEvent) {
  // Don't handle if user is typing in an input
  if ((event.target as HTMLElement).tagName === 'INPUT') return

  switch (event.key) {
    case 'ArrowLeft':
      if (currentPage.value > 1) {
        handlePageChange(currentPage.value - 1)
      }
      break
    case 'ArrowRight':
      if (currentPage.value < totalPages.value) {
        handlePageChange(currentPage.value + 1)
      }
      break
    case 'Home':
      handlePageChange(1)
      break
    case 'End':
      handlePageChange(totalPages.value)
      break
    case '+':
    case '=':
      if (zoom.value < 200) {
        const levels = [15, 25, 50, 75, 100, 125, 150, 200]
        const nextLevel = levels.find(l => l > zoom.value)
        if (nextLevel) zoom.value = nextLevel
      }
      break
    case '-':
      if (zoom.value > 15) {
        const levels = [15, 25, 50, 75, 100, 125, 150, 200].reverse()
        const nextLevel = levels.find(l => l < zoom.value)
        if (nextLevel) zoom.value = nextLevel
      }
      break
    case '0':
      handleResetView()
      break
  }
}

// Lifecycle
onMounted(() => {
  if (props.documentId) {
    loadDocument(props.documentId)
  }
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="pdf-viewer flex flex-col h-full bg-gray-100">
    <!-- Toolbar -->
    <ViewerToolbar
      :documents="documents"
      :current-document-id="currentDocumentId"
      :zoom="zoom"
      :total-pages="totalPages"
      :current-page="currentPage"
      @select-document="handleDocumentSelect"
      @zoom-change="handleZoomChange"
      @reset-view="handleResetView"
    />

    <!-- Main content area -->
    <div class="flex-1 relative min-h-0">
      <!-- Loading overlay -->
      <div
        v-if="loading"
        class="absolute inset-0 bg-white/80 flex items-center justify-center z-10"
      >
        <div class="flex flex-col items-center gap-3">
          <svg class="animate-spin h-10 w-10 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span class="text-gray-600">Loading document...</span>
        </div>
      </div>

      <!-- Error message -->
      <div
        v-if="error && !loading"
        class="absolute top-4 left-1/2 -translate-x-1/2 z-20"
      >
        <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm flex items-center gap-2">
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {{ error }}
        </div>
      </div>

      <!-- No document selected state -->
      <div
        v-if="!currentDocumentId && !loading"
        class="absolute inset-0 flex items-center justify-center"
      >
        <div class="text-center text-gray-500">
          <svg class="mx-auto h-16 w-16 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p class="text-lg font-medium">No document selected</p>
          <p class="text-sm mt-1">Select a document from the dropdown above or navigate from search results.</p>
        </div>
      </div>

      <!-- PDF Canvas -->
      <PdfCanvas
        v-if="currentDocumentId && imageUrl"
        ref="canvasRef"
        :image-src="imageUrl"
        :zoom="zoom"
        @pan-change="handlePanChange"
        @image-error="handleImageError"
        @image-loaded="handleImageLoaded"
      />
    </div>

    <!-- Page Navigator -->
    <PageNavigator
      v-if="totalPages > 0"
      :current-page="currentPage"
      :total-pages="totalPages"
      @page-change="handlePageChange"
    />
  </div>
</template>

<style scoped>
.pdf-viewer {
  /* Ensure the viewer takes full height */
  height: 100%;
}
</style>
