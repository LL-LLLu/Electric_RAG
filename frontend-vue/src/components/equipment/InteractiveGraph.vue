<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ArrowPathIcon, MagnifyingGlassPlusIcon, MagnifyingGlassMinusIcon } from '@heroicons/vue/24/outline'
import type { GraphNode, GraphEdge } from '@/api/equipment'

const props = defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
  centerTag: string
}>()

const emit = defineEmits<{
  nodeClick: [tag: string]
  edgeHover: [edge: GraphEdge | null]
}>()

// Canvas and state
const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const hoveredNode = ref<string | null>(null)
const hoveredEdge = ref<GraphEdge | null>(null)
const selectedNode = ref<string | null>(null)
const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const isDragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const dragNode = ref<string | null>(null)
const nodePositions = ref<Map<string, { x: number; y: number }>>(new Map())

// Color scheme for different edge types
const edgeColors: Record<string, string> = {
  feeds: '#ef4444',      // red
  controls: '#3b82f6',   // blue
  protects: '#22c55e',   // green
  monitors: '#f59e0b',   // amber
  drives: '#8b5cf6',     // purple
  mechanical: '#6b7280', // gray
}

const nodeColors: Record<string, string> = {
  ELECTRICAL: '#ef4444',
  CONTROL: '#3b82f6',
  MECHANICAL: '#6b7280',
  unknown: '#9ca3af',
}

// Initialize node positions in a circular layout
function initializePositions() {
  if (!canvasRef.value) return

  const canvas = canvasRef.value
  const centerX = canvas.width / 2
  const centerY = canvas.height / 2
  const radius = Math.min(canvas.width, canvas.height) * 0.35

  const newPositions = new Map<string, { x: number; y: number }>()

  // Place center node at center
  const centerNode = props.nodes.find(n => n.isCenter)
  if (centerNode) {
    newPositions.set(centerNode.id, { x: centerX, y: centerY })
  }

  // Place other nodes in a circle
  const otherNodes = props.nodes.filter(n => !n.isCenter)
  const angleStep = (2 * Math.PI) / Math.max(otherNodes.length, 1)

  otherNodes.forEach((node, i) => {
    const angle = angleStep * i - Math.PI / 2
    newPositions.set(node.id, {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    })
  })

  nodePositions.value = newPositions
}

// Draw the graph
function draw() {
  if (!canvasRef.value) return

  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Clear canvas
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Apply zoom and pan
  ctx.save()
  ctx.translate(pan.value.x, pan.value.y)
  ctx.scale(zoom.value, zoom.value)

  // Draw edges
  props.edges.forEach(edge => {
    const fromPos = nodePositions.value.get(edge.from)
    const toPos = nodePositions.value.get(edge.to)
    if (!fromPos || !toPos) return

    const isHovered = hoveredEdge.value === edge
    const color = edgeColors[edge.type] || '#6b7280'

    ctx.beginPath()
    ctx.moveTo(fromPos.x, fromPos.y)
    ctx.lineTo(toPos.x, toPos.y)
    ctx.strokeStyle = isHovered ? color : color + '80'
    ctx.lineWidth = isHovered ? 3 : 2
    ctx.stroke()

    // Draw arrow
    const angle = Math.atan2(toPos.y - fromPos.y, toPos.x - fromPos.x)
    const arrowLength = 12
    const arrowX = toPos.x - 25 * Math.cos(angle)
    const arrowY = toPos.y - 25 * Math.sin(angle)

    ctx.beginPath()
    ctx.moveTo(arrowX, arrowY)
    ctx.lineTo(
      arrowX - arrowLength * Math.cos(angle - Math.PI / 6),
      arrowY - arrowLength * Math.sin(angle - Math.PI / 6)
    )
    ctx.lineTo(
      arrowX - arrowLength * Math.cos(angle + Math.PI / 6),
      arrowY - arrowLength * Math.sin(angle + Math.PI / 6)
    )
    ctx.closePath()
    ctx.fillStyle = color
    ctx.fill()

    // Draw edge label
    const midX = (fromPos.x + toPos.x) / 2
    const midY = (fromPos.y + toPos.y) / 2
    ctx.font = '10px sans-serif'
    ctx.fillStyle = '#4b5563'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'

    // Background for label
    const labelWidth = ctx.measureText(edge.label).width + 6
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(midX - labelWidth / 2, midY - 7, labelWidth, 14)
    ctx.fillStyle = color
    ctx.fillText(edge.label, midX, midY)
  })

  // Draw nodes
  props.nodes.forEach(node => {
    const pos = nodePositions.value.get(node.id)
    if (!pos) return

    const isHovered = hoveredNode.value === node.id
    const isSelected = selectedNode.value === node.id
    const isCenter = node.isCenter
    const radius = isCenter ? 30 : 22

    // Node circle
    ctx.beginPath()
    ctx.arc(pos.x, pos.y, radius, 0, 2 * Math.PI)

    // Fill color based on type
    let fillColor: string = nodeColors[node.type] || nodeColors.unknown || '#9ca3af'
    if (isCenter) fillColor = '#1d4ed8'

    ctx.fillStyle = fillColor
    ctx.fill()

    // Border
    ctx.strokeStyle = isHovered || isSelected ? '#1f2937' : '#ffffff'
    ctx.lineWidth = isHovered || isSelected ? 3 : 2
    ctx.stroke()

    // Label
    ctx.font = isCenter ? 'bold 11px sans-serif' : '10px sans-serif'
    ctx.fillStyle = '#ffffff'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(node.label, pos.x, pos.y)
  })

  ctx.restore()
}

// Handle mouse move for hover effects
function handleMouseMove(e: MouseEvent) {
  if (!canvasRef.value) return

  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  const x = (e.clientX - rect.left - pan.value.x) / zoom.value
  const y = (e.clientY - rect.top - pan.value.y) / zoom.value

  // Check if dragging a node
  if (isDragging.value && dragNode.value) {
    nodePositions.value.set(dragNode.value, { x, y })
    draw()
    return
  }

  // Check if panning
  if (isDragging.value && !dragNode.value) {
    pan.value = {
      x: e.clientX - dragStart.value.x,
      y: e.clientY - dragStart.value.y,
    }
    draw()
    return
  }

  // Check node hover
  let foundNode = false
  for (const node of props.nodes) {
    const pos = nodePositions.value.get(node.id)
    if (!pos) continue

    const radius = node.isCenter ? 30 : 22
    const distance = Math.sqrt((x - pos.x) ** 2 + (y - pos.y) ** 2)

    if (distance <= radius) {
      hoveredNode.value = node.id
      hoveredEdge.value = null
      foundNode = true
      canvas.style.cursor = 'pointer'
      break
    }
  }

  if (!foundNode) {
    hoveredNode.value = null
    canvas.style.cursor = 'grab'

    // Check edge hover
    let foundEdge = false
    for (const edge of props.edges) {
      const fromPos = nodePositions.value.get(edge.from)
      const toPos = nodePositions.value.get(edge.to)
      if (!fromPos || !toPos) continue

      // Distance from point to line segment
      const distance = pointToLineDistance(x, y, fromPos.x, fromPos.y, toPos.x, toPos.y)
      if (distance < 10) {
        hoveredEdge.value = edge
        emit('edgeHover', edge)
        foundEdge = true
        break
      }
    }

    if (!foundEdge && hoveredEdge.value) {
      hoveredEdge.value = null
      emit('edgeHover', null)
    }
  }

  draw()
}

// Distance from point to line segment
function pointToLineDistance(px: number, py: number, x1: number, y1: number, x2: number, y2: number): number {
  const A = px - x1
  const B = py - y1
  const C = x2 - x1
  const D = y2 - y1

  const dot = A * C + B * D
  const lenSq = C * C + D * D
  let param = -1

  if (lenSq !== 0) param = dot / lenSq

  let xx, yy

  if (param < 0) {
    xx = x1
    yy = y1
  } else if (param > 1) {
    xx = x2
    yy = y2
  } else {
    xx = x1 + param * C
    yy = y1 + param * D
  }

  const dx = px - xx
  const dy = py - yy
  return Math.sqrt(dx * dx + dy * dy)
}

// Handle mouse down
function handleMouseDown(e: MouseEvent) {
  if (!canvasRef.value) return

  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  const x = (e.clientX - rect.left - pan.value.x) / zoom.value
  const y = (e.clientY - rect.top - pan.value.y) / zoom.value

  // Check if clicking on a node
  for (const node of props.nodes) {
    const pos = nodePositions.value.get(node.id)
    if (!pos) continue

    const radius = node.isCenter ? 30 : 22
    const distance = Math.sqrt((x - pos.x) ** 2 + (y - pos.y) ** 2)

    if (distance <= radius) {
      dragNode.value = node.id
      isDragging.value = true
      canvas.style.cursor = 'grabbing'
      return
    }
  }

  // Start panning
  isDragging.value = true
  dragStart.value = {
    x: e.clientX - pan.value.x,
    y: e.clientY - pan.value.y,
  }
  canvas.style.cursor = 'grabbing'
}

// Handle mouse up
function handleMouseUp() {
  if (!canvasRef.value) return

  isDragging.value = false
  canvasRef.value.style.cursor = 'grab'

  // If a node was clicked (not dragged), emit click event
  if (dragNode.value && hoveredNode.value === dragNode.value) {
    emit('nodeClick', dragNode.value)
  }

  dragNode.value = null
}

// Handle double-click to navigate
function handleDoubleClick(e: MouseEvent) {
  if (!canvasRef.value) return

  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  const x = (e.clientX - rect.left - pan.value.x) / zoom.value
  const y = (e.clientY - rect.top - pan.value.y) / zoom.value

  for (const node of props.nodes) {
    const pos = nodePositions.value.get(node.id)
    if (!pos) continue

    const radius = node.isCenter ? 30 : 22
    const distance = Math.sqrt((x - pos.x) ** 2 + (y - pos.y) ** 2)

    if (distance <= radius) {
      emit('nodeClick', node.id)
      return
    }
  }
}

// Zoom controls
function zoomIn() {
  zoom.value = Math.min(zoom.value * 1.2, 3)
  draw()
}

function zoomOut() {
  zoom.value = Math.max(zoom.value / 1.2, 0.3)
  draw()
}

function resetView() {
  zoom.value = 1
  pan.value = { x: 0, y: 0 }
  initializePositions()
  draw()
}

// Handle wheel for zoom
function handleWheel(e: WheelEvent) {
  e.preventDefault()
  if (e.deltaY < 0) {
    zoom.value = Math.min(zoom.value * 1.1, 3)
  } else {
    zoom.value = Math.max(zoom.value / 1.1, 0.3)
  }
  draw()
}

// Handle resize
function handleResize() {
  if (!canvasRef.value || !containerRef.value) return

  canvasRef.value.width = containerRef.value.clientWidth
  canvasRef.value.height = containerRef.value.clientHeight
  initializePositions()
  draw()
}

// Watch for prop changes
watch(() => [props.nodes, props.edges], () => {
  nextTick(() => {
    initializePositions()
    draw()
  })
}, { deep: true })

onMounted(() => {
  if (containerRef.value && canvasRef.value) {
    canvasRef.value.width = containerRef.value.clientWidth
    canvasRef.value.height = containerRef.value.clientHeight
    initializePositions()
    draw()
  }

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

// Edge details display
const edgeDetails = computed(() => {
  if (!hoveredEdge.value) return null

  const details = hoveredEdge.value.details
  const parts: string[] = []

  if (details.voltage) parts.push(`Voltage: ${details.voltage}`)
  if (details.wire_size) parts.push(`Wire: ${details.wire_size}`)
  if (details.breaker) parts.push(`Breaker: ${details.breaker}`)
  if (details.signal_type) parts.push(`Signal: ${details.signal_type}`)
  if (details.io_type) parts.push(`I/O: ${details.io_type}`)
  if (details.medium) parts.push(`Medium: ${details.medium}`)
  if (details.pipe_size) parts.push(`Pipe: ${details.pipe_size}`)
  if (details.function) parts.push(`Function: ${details.function}`)

  return parts.length > 0 ? parts : null
})
</script>

<template>
  <div class="interactive-graph relative">
    <!-- Controls -->
    <div class="absolute top-2 right-2 z-10 flex gap-1">
      <button
        type="button"
        class="p-1.5 bg-white rounded border border-gray-200 hover:bg-gray-50 shadow-sm"
        title="Zoom In"
        @click="zoomIn"
      >
        <MagnifyingGlassPlusIcon class="h-4 w-4 text-gray-600" />
      </button>
      <button
        type="button"
        class="p-1.5 bg-white rounded border border-gray-200 hover:bg-gray-50 shadow-sm"
        title="Zoom Out"
        @click="zoomOut"
      >
        <MagnifyingGlassMinusIcon class="h-4 w-4 text-gray-600" />
      </button>
      <button
        type="button"
        class="p-1.5 bg-white rounded border border-gray-200 hover:bg-gray-50 shadow-sm"
        title="Reset View"
        @click="resetView"
      >
        <ArrowPathIcon class="h-4 w-4 text-gray-600" />
      </button>
    </div>

    <!-- Legend -->
    <div class="absolute bottom-2 left-2 z-10 bg-white/90 rounded border border-gray-200 p-2 text-xs shadow-sm">
      <div class="font-semibold mb-1">Connection Types</div>
      <div class="grid grid-cols-2 gap-x-3 gap-y-0.5">
        <div class="flex items-center gap-1">
          <span class="w-3 h-0.5 bg-red-500"></span>
          <span>Feeds</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-0.5 bg-blue-500"></span>
          <span>Controls</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-0.5 bg-green-500"></span>
          <span>Protects</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-0.5 bg-amber-500"></span>
          <span>Monitors</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-0.5 bg-purple-500"></span>
          <span>Drives</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-0.5 bg-gray-500"></span>
          <span>Mechanical</span>
        </div>
      </div>
    </div>

    <!-- Edge details tooltip -->
    <Transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="edgeDetails"
        class="absolute top-2 left-2 z-10 bg-white rounded-lg border border-gray-200 p-3 shadow-lg max-w-xs"
      >
        <div class="font-semibold text-sm mb-1">
          {{ hoveredEdge?.from }} → {{ hoveredEdge?.to }}
        </div>
        <div class="text-xs text-gray-600 space-y-0.5">
          <div v-for="detail in edgeDetails" :key="detail">{{ detail }}</div>
        </div>
      </div>
    </Transition>

    <!-- Canvas -->
    <div ref="containerRef" class="w-full h-64 bg-gray-50 rounded-lg border border-gray-200">
      <canvas
        ref="canvasRef"
        class="w-full h-full cursor-grab"
        @mousemove="handleMouseMove"
        @mousedown="handleMouseDown"
        @mouseup="handleMouseUp"
        @mouseleave="handleMouseUp"
        @dblclick="handleDoubleClick"
        @wheel="handleWheel"
      />
    </div>

    <!-- Instructions -->
    <div class="mt-2 text-xs text-gray-500 text-center">
      Double-click a node to navigate. Drag nodes to reposition. Scroll to zoom.
    </div>
  </div>
</template>

<style scoped>
.interactive-graph {
  user-select: none;
}
</style>
