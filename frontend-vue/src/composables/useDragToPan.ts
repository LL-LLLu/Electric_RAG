import { ref, reactive, type Ref } from 'vue'
import type { PanPosition } from '@/types'

export interface UseDragToPanOptions {
  /** Initial pan position */
  initialPosition?: PanPosition
}

export interface UseDragToPanReturn {
  /** Current pan position */
  panPosition: PanPosition
  /** Whether user is currently dragging */
  isDragging: Ref<boolean>
  /** Start drag handler - call on mousedown */
  startDrag: (event: MouseEvent) => void
  /** Drag handler - call on mousemove */
  onDrag: (event: MouseEvent) => void
  /** End drag handler - call on mouseup/mouseleave */
  endDrag: () => void
  /** Reset pan position to origin */
  resetPan: () => void
  /** Set pan position programmatically */
  setPanPosition: (x: number, y: number) => void
}

/**
 * Composable for drag-to-pan functionality
 * Provides smooth drag-based panning for images and canvas elements
 */
export function useDragToPan(options: UseDragToPanOptions = {}): UseDragToPanReturn {
  const { initialPosition = { x: 0, y: 0 } } = options

  // State
  const isDragging = ref(false)
  const panPosition = reactive<PanPosition>({
    x: initialPosition.x,
    y: initialPosition.y
  })

  // Internal tracking for drag delta calculation
  let startMouseX = 0
  let startMouseY = 0
  let startPanX = 0
  let startPanY = 0

  /**
   * Start drag - captures initial mouse and pan positions
   */
  function startDrag(event: MouseEvent) {
    // Only respond to left mouse button
    if (event.button !== 0) return

    isDragging.value = true
    startMouseX = event.clientX
    startMouseY = event.clientY
    startPanX = panPosition.x
    startPanY = panPosition.y

    // Prevent text selection during drag
    event.preventDefault()
  }

  /**
   * Handle drag movement - calculates delta and updates position
   */
  function onDrag(event: MouseEvent) {
    if (!isDragging.value) return

    const deltaX = event.clientX - startMouseX
    const deltaY = event.clientY - startMouseY

    panPosition.x = startPanX + deltaX
    panPosition.y = startPanY + deltaY
  }

  /**
   * End drag - stops tracking
   */
  function endDrag() {
    isDragging.value = false
  }

  /**
   * Reset pan position to origin (0, 0)
   */
  function resetPan() {
    panPosition.x = 0
    panPosition.y = 0
  }

  /**
   * Set pan position programmatically
   */
  function setPanPosition(x: number, y: number) {
    panPosition.x = x
    panPosition.y = y
  }

  return {
    panPosition,
    isDragging,
    startDrag,
    onDrag,
    endDrag,
    resetPan,
    setPanPosition
  }
}

export default useDragToPan
