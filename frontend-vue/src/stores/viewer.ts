import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'

export interface ViewerDocument {
  id: string
  filename: string
  page_count: number
}

export interface PanPosition {
  x: number
  y: number
}

export const useViewerStore = defineStore('viewer', () => {
  // Current document
  const currentDocument = ref<ViewerDocument | null>(null)
  const loading = ref(false)

  // Page navigation
  const pageNumber = ref(1)

  // Zoom and pan
  const zoomLevel = ref(1)
  const panPosition = reactive<PanPosition>({ x: 0, y: 0 })

  // Zoom constraints
  const minZoom = 0.25
  const maxZoom = 4
  const zoomStep = 0.25

  // Computed
  const hasDocument = computed(() => currentDocument.value !== null)
  const totalPages = computed(() => currentDocument.value?.page_count ?? 0)
  const canGoNext = computed(() => pageNumber.value < totalPages.value)
  const canGoPrevious = computed(() => pageNumber.value > 1)
  const canZoomIn = computed(() => zoomLevel.value < maxZoom)
  const canZoomOut = computed(() => zoomLevel.value > minZoom)
  const zoomPercentage = computed(() => Math.round(zoomLevel.value * 100))

  // Actions
  function setDocument(doc: ViewerDocument | null) {
    currentDocument.value = doc
    // Reset view state when document changes
    pageNumber.value = 1
    resetZoom()
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function setPageNumber(page: number) {
    if (currentDocument.value) {
      pageNumber.value = Math.max(1, Math.min(page, currentDocument.value.page_count))
    }
  }

  function nextPage() {
    if (canGoNext.value) {
      pageNumber.value++
    }
  }

  function previousPage() {
    if (canGoPrevious.value) {
      pageNumber.value--
    }
  }

  function goToFirstPage() {
    pageNumber.value = 1
  }

  function goToLastPage() {
    if (currentDocument.value) {
      pageNumber.value = currentDocument.value.page_count
    }
  }

  function setZoomLevel(zoom: number) {
    zoomLevel.value = Math.max(minZoom, Math.min(maxZoom, zoom))
  }

  function zoomIn() {
    if (canZoomIn.value) {
      zoomLevel.value = Math.min(maxZoom, zoomLevel.value + zoomStep)
    }
  }

  function zoomOut() {
    if (canZoomOut.value) {
      zoomLevel.value = Math.max(minZoom, zoomLevel.value - zoomStep)
    }
  }

  function resetZoom() {
    zoomLevel.value = 1
    panPosition.x = 0
    panPosition.y = 0
  }

  function fitToWidth() {
    // This will be implemented by the viewer component
    // based on container width and image dimensions
    zoomLevel.value = 1
  }

  function setPanPosition(x: number, y: number) {
    panPosition.x = x
    panPosition.y = y
  }

  function resetPan() {
    panPosition.x = 0
    panPosition.y = 0
  }

  function reset() {
    currentDocument.value = null
    pageNumber.value = 1
    zoomLevel.value = 1
    panPosition.x = 0
    panPosition.y = 0
    loading.value = false
  }

  return {
    currentDocument,
    loading,
    pageNumber,
    zoomLevel,
    panPosition,
    minZoom,
    maxZoom,
    zoomStep,
    hasDocument,
    totalPages,
    canGoNext,
    canGoPrevious,
    canZoomIn,
    canZoomOut,
    zoomPercentage,
    setDocument,
    setLoading,
    setPageNumber,
    nextPage,
    previousPage,
    goToFirstPage,
    goToLastPage,
    setZoomLevel,
    zoomIn,
    zoomOut,
    resetZoom,
    fitToWidth,
    setPanPosition,
    resetPan,
    reset
  }
})
