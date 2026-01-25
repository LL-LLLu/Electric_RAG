<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon
} from '@heroicons/vue/24/outline'

const props = defineProps<{
  /** Current page number (1-indexed) */
  currentPage: number
  /** Total number of pages */
  totalPages: number
}>()

const emit = defineEmits<{
  /** Emitted when page changes */
  pageChange: [pageNumber: number]
}>()

// Local input value for the page number input
const inputValue = ref(props.currentPage.toString())

// Sync input value with prop changes
watch(() => props.currentPage, (newPage) => {
  inputValue.value = newPage.toString()
})

// Computed navigation states
const canGoFirst = () => props.currentPage > 1
const canGoPrevious = () => props.currentPage > 1
const canGoNext = () => props.currentPage < props.totalPages
const canGoLast = () => props.currentPage < props.totalPages

function goToFirst() {
  if (canGoFirst()) {
    emit('pageChange', 1)
  }
}

function goPrevious() {
  if (canGoPrevious()) {
    emit('pageChange', props.currentPage - 1)
  }
}

function goNext() {
  if (canGoNext()) {
    emit('pageChange', props.currentPage + 1)
  }
}

function goToLast() {
  if (canGoLast()) {
    emit('pageChange', props.totalPages)
  }
}

function handleInputChange() {
  const pageNum = parseInt(inputValue.value, 10)
  if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= props.totalPages) {
    emit('pageChange', pageNum)
  } else {
    // Reset to current page if invalid
    inputValue.value = props.currentPage.toString()
  }
}

function handleInputKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    handleInputChange()
    ;(event.target as HTMLInputElement).blur()
  } else if (event.key === 'Escape') {
    inputValue.value = props.currentPage.toString()
    ;(event.target as HTMLInputElement).blur()
  }
}

// Handle input blur
function handleInputBlur() {
  handleInputChange()
}
</script>

<template>
  <div class="page-navigator flex items-center gap-2 bg-white border-t border-gray-200 px-4 py-2">
    <!-- First Page Button -->
    <button
      type="button"
      :disabled="!canGoFirst()"
      class="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      title="First page"
      @click="goToFirst"
    >
      <ChevronDoubleLeftIcon class="h-5 w-5 text-gray-600" />
    </button>

    <!-- Previous Page Button -->
    <button
      type="button"
      :disabled="!canGoPrevious()"
      class="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      title="Previous page"
      @click="goPrevious"
    >
      <ChevronLeftIcon class="h-5 w-5 text-gray-600" />
    </button>

    <!-- Page Input -->
    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">Page</span>
      <input
        v-model="inputValue"
        type="text"
        class="w-14 px-2 py-1 text-center border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        :disabled="totalPages === 0"
        @keydown="handleInputKeydown"
        @blur="handleInputBlur"
      />
      <span class="text-sm text-gray-600">of {{ totalPages }}</span>
    </div>

    <!-- Next Page Button -->
    <button
      type="button"
      :disabled="!canGoNext()"
      class="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      title="Next page"
      @click="goNext"
    >
      <ChevronRightIcon class="h-5 w-5 text-gray-600" />
    </button>

    <!-- Last Page Button -->
    <button
      type="button"
      :disabled="!canGoLast()"
      class="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      title="Last page"
      @click="goToLast"
    >
      <ChevronDoubleRightIcon class="h-5 w-5 text-gray-600" />
    </button>

    <!-- Keyboard shortcuts hint -->
    <div class="ml-4 text-xs text-gray-400 hidden sm:block">
      <span class="px-1.5 py-0.5 bg-gray-100 rounded text-gray-500 font-mono">←</span>
      <span class="px-1.5 py-0.5 bg-gray-100 rounded text-gray-500 font-mono ml-1">→</span>
      <span class="ml-1">to navigate</span>
    </div>
  </div>
</template>

<style scoped>
.page-navigator {
  min-height: 48px;
}

/* Remove spinner buttons from number input */
input::-webkit-outer-spin-button,
input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

input[type=number] {
  -moz-appearance: textfield;
}
</style>
