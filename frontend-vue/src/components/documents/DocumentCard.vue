<script setup lang="ts">
import { computed } from 'vue'
import { DocumentIcon, ChevronRightIcon } from '@heroicons/vue/24/outline'
import type { Document } from '@/types'

const props = defineProps<{
  document: Document
}>()

const emit = defineEmits<{
  select: [document: Document]
}>()

function handleClick() {
  emit('select', props.document)
}

// Computed properties for display
const displayFilename = computed(() => {
  return props.document.original_filename || props.document.filename
})

const formattedDate = computed(() => {
  const date = new Date(props.document.upload_date)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
})

const formattedFileSize = computed(() => {
  const bytes = props.document.file_size
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
})

// Status badge configuration
const statusConfig = computed(() => {
  switch (props.document.processed) {
    case 0:
      return {
        label: 'Pending',
        classes: 'bg-yellow-100 text-yellow-800'
      }
    case 1:
      return {
        label: 'Processing',
        classes: 'bg-blue-100 text-blue-800'
      }
    case 2:
      return {
        label: 'Complete',
        classes: 'bg-green-100 text-green-800'
      }
    case -1:
      return {
        label: 'Error',
        classes: 'bg-red-100 text-red-800'
      }
    default:
      return {
        label: 'Unknown',
        classes: 'bg-gray-100 text-gray-800'
      }
  }
})
</script>

<template>
  <div
    class="document-card bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md hover:border-blue-300 transition-all cursor-pointer"
    @click="handleClick"
  >
    <div class="p-4">
      <!-- Header with Icon and Filename -->
      <div class="flex items-start justify-between mb-3">
        <div class="flex items-start gap-3 min-w-0 flex-1">
          <div class="p-2 bg-blue-50 rounded-lg flex-shrink-0">
            <DocumentIcon class="h-5 w-5 text-blue-600" />
          </div>
          <div class="min-w-0 flex-1">
            <h3 class="text-sm font-semibold text-gray-900 truncate" :title="displayFilename">
              {{ displayFilename }}
            </h3>
            <p class="text-xs text-gray-500 mt-0.5">
              {{ formattedFileSize }}
            </p>
          </div>
        </div>
        <ChevronRightIcon class="h-5 w-5 text-gray-400 flex-shrink-0" />
      </div>

      <!-- Status Badge -->
      <div class="mb-3">
        <span
          class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
          :class="statusConfig.classes"
        >
          {{ statusConfig.label }}
        </span>
      </div>

      <!-- Document Info -->
      <div class="flex flex-wrap gap-3 text-xs text-gray-500">
        <span class="flex items-center gap-1">
          <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {{ document.page_count }} {{ document.page_count === 1 ? 'page' : 'pages' }}
        </span>
        <span class="flex items-center gap-1">
          <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {{ formattedDate }}
        </span>
      </div>

      <!-- Processing Progress (for processing status) -->
      <div
        v-if="document.processed === 1 && document.page_count > 0"
        class="mt-3 pt-3 border-t border-gray-100"
      >
        <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
          <span>Processing progress</span>
          <span>{{ document.pages_processed }}/{{ document.page_count }}</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-1.5">
          <div
            class="bg-blue-600 h-1.5 rounded-full transition-all"
            :style="{ width: `${(document.pages_processed / document.page_count) * 100}%` }"
          ></div>
        </div>
      </div>

      <!-- Error Message -->
      <div
        v-if="document.processed === -1 && document.processing_error"
        class="mt-3 pt-3 border-t border-gray-100"
      >
        <p class="text-xs text-red-600 line-clamp-2">
          {{ document.processing_error }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
