<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { XMarkIcon, DocumentIcon, EyeIcon } from '@heroicons/vue/24/outline'
import type { DocumentDetail } from '@/types'
import PagesList from './PagesList.vue'

const props = defineProps<{
  document: DocumentDetail
}>()

const emit = defineEmits<{
  close: []
}>()

const router = useRouter()

function handleClose() {
  emit('close')
}

function openInViewer() {
  router.push({
    name: 'viewer',
    params: {
      docId: props.document.id,
      pageNum: 1
    }
  })
}

// Computed properties for display
const displayFilename = computed(() => {
  return props.document.original_filename || props.document.filename
})

const formattedDate = computed(() => {
  const date = new Date(props.document.upload_date)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
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
  <div class="document-detail bg-white rounded-lg shadow-lg border border-gray-200">
    <!-- Header -->
    <div class="flex items-start justify-between p-4 border-b border-gray-200 bg-gray-50 rounded-t-lg">
      <div class="flex items-start gap-3 min-w-0 flex-1">
        <div class="p-2 bg-blue-100 rounded-lg flex-shrink-0">
          <DocumentIcon class="h-6 w-6 text-blue-600" />
        </div>
        <div class="min-w-0 flex-1">
          <h2 class="text-lg font-bold text-gray-900 break-words">
            {{ displayFilename }}
          </h2>
          <span
            class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium mt-1"
            :class="statusConfig.classes"
          >
            {{ statusConfig.label }}
          </span>
        </div>
      </div>
      <button
        type="button"
        class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded-full transition-colors flex-shrink-0"
        @click="handleClose"
        aria-label="Close detail view"
      >
        <XMarkIcon class="h-5 w-5" />
      </button>
    </div>

    <!-- Content -->
    <div class="p-4 space-y-6 max-h-[calc(100vh-200px)] overflow-y-auto">
      <!-- Open in Viewer Button -->
      <button
        type="button"
        class="w-full inline-flex items-center justify-center gap-2 px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
        @click="openInViewer"
      >
        <EyeIcon class="h-4 w-4" />
        Open in Viewer
      </button>

      <!-- Document Info Section -->
      <div class="space-y-4">
        <h4 class="text-sm font-semibold text-gray-700">Document Information</h4>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <p class="text-xs text-gray-500">File Size</p>
            <p class="text-sm text-gray-900 font-medium">{{ formattedFileSize }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500">Pages</p>
            <p class="text-sm text-gray-900 font-medium">{{ document.page_count }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500">Equipment Found</p>
            <p class="text-sm text-gray-900 font-medium">{{ document.equipment_count }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500">Upload Date</p>
            <p class="text-sm text-gray-900 font-medium">{{ formattedDate }}</p>
          </div>
        </div>

        <!-- Processing Progress (for processing status) -->
        <div
          v-if="document.processed === 1 && document.page_count > 0"
          class="p-3 bg-blue-50 rounded-lg"
        >
          <div class="flex items-center justify-between text-sm text-blue-700 mb-2">
            <span>Processing in progress...</span>
            <span>{{ document.pages_processed }}/{{ document.page_count }} pages</span>
          </div>
          <div class="w-full bg-blue-200 rounded-full h-2">
            <div
              class="bg-blue-600 h-2 rounded-full transition-all"
              :style="{ width: `${(document.pages_processed / document.page_count) * 100}%` }"
            ></div>
          </div>
        </div>

        <!-- Error Message -->
        <div
          v-if="document.processed === -1 && document.processing_error"
          class="p-3 bg-red-50 rounded-lg"
        >
          <p class="text-sm text-red-700 font-medium mb-1">Processing Error</p>
          <p class="text-sm text-red-600">{{ document.processing_error }}</p>
        </div>
      </div>

      <!-- Divider -->
      <hr class="border-gray-200" />

      <!-- Pages Section -->
      <PagesList
        :pages="document.pages"
        :document-id="document.id"
      />
    </div>
  </div>
</template>
