<script setup lang="ts">
import type { Document } from '@/types'
import {
  DocumentIcon,
  ArrowPathIcon,
  TrashIcon,
  EyeIcon
} from '@heroicons/vue/24/outline'

defineProps<{
  documents: Document[]
  loading?: boolean
}>()

const emit = defineEmits<{
  retry: [id: number]
  delete: [id: number]
  view: [id: number]
}>()

function getStatusBadge(processed: number) {
  switch (processed) {
    case 0:
      return { label: 'Pending', class: 'bg-yellow-100 text-yellow-800' }
    case 1:
      return { label: 'Processing', class: 'bg-blue-100 text-blue-800' }
    case 2:
      return { label: 'Complete', class: 'bg-green-100 text-green-800' }
    case -1:
      return { label: 'Error', class: 'bg-red-100 text-red-800' }
    default:
      return { label: 'Unknown', class: 'bg-gray-100 text-gray-800' }
  }
}

function formatDate(dateString: string) {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatFileSize(bytes: number) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}
</script>

<template>
  <div class="document-list">
    <h3 class="text-lg font-semibold text-gray-900 mb-4">Recent Documents</h3>

    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center py-8">
      <ArrowPathIcon class="h-6 w-6 text-gray-400 animate-spin" />
      <span class="ml-2 text-sm text-gray-500">Loading documents...</span>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="documents.length === 0"
      class="text-center py-8 bg-gray-50 rounded-lg border border-dashed border-gray-300"
    >
      <DocumentIcon class="h-12 w-12 mx-auto text-gray-400 mb-3" />
      <p class="text-gray-500">No documents uploaded yet</p>
      <p class="text-sm text-gray-400 mt-1">Upload a PDF to get started</p>
    </div>

    <!-- Document List -->
    <div v-else class="space-y-3">
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="bg-white rounded-lg border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow"
      >
        <div class="flex items-start justify-between">
          <!-- Document Info -->
          <div class="flex items-start space-x-3 min-w-0 flex-1">
            <div class="flex-shrink-0 mt-1">
              <DocumentIcon class="h-8 w-8 text-gray-400" />
            </div>

            <div class="min-w-0 flex-1">
              <!-- Filename -->
              <h4 class="text-sm font-medium text-gray-900 truncate">
                {{ doc.original_filename }}
              </h4>

              <!-- Metadata -->
              <div class="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
                <span>{{ doc.page_count }} page{{ doc.page_count !== 1 ? 's' : '' }}</span>
                <span>{{ formatFileSize(doc.file_size) }}</span>
                <span>{{ formatDate(doc.upload_date) }}</span>
              </div>

              <!-- Document Title/Number if available -->
              <div
                v-if="doc.title || doc.drawing_number"
                class="mt-1 text-xs text-gray-600"
              >
                <span v-if="doc.title">{{ doc.title }}</span>
                <span v-if="doc.title && doc.drawing_number"> - </span>
                <span v-if="doc.drawing_number">{{ doc.drawing_number }}</span>
              </div>

              <!-- Error Message -->
              <p
                v-if="doc.processed === -1 && doc.processing_error"
                class="mt-1 text-xs text-red-600"
              >
                {{ doc.processing_error }}
              </p>
            </div>
          </div>

          <!-- Status Badge and Actions -->
          <div class="flex items-center space-x-3 ml-4 flex-shrink-0">
            <!-- Status Badge -->
            <span
              class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
              :class="getStatusBadge(doc.processed).class"
            >
              <ArrowPathIcon
                v-if="doc.processed === 1"
                class="h-3 w-3 mr-1 animate-spin"
              />
              {{ getStatusBadge(doc.processed).label }}
            </span>

            <!-- Action Buttons -->
            <div class="flex items-center space-x-1">
              <!-- View Button (only when complete) -->
              <button
                v-if="doc.processed === 2"
                type="button"
                class="p-1.5 rounded-md text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                title="View document"
                @click="emit('view', doc.id)"
              >
                <EyeIcon class="h-5 w-5" />
              </button>

              <!-- Retry Button (only when error) -->
              <button
                v-if="doc.processed === -1"
                type="button"
                class="p-1.5 rounded-md text-gray-400 hover:text-yellow-600 hover:bg-yellow-50 transition-colors"
                title="Retry processing"
                @click="emit('retry', doc.id)"
              >
                <ArrowPathIcon class="h-5 w-5" />
              </button>

              <!-- Delete Button -->
              <button
                type="button"
                class="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                title="Delete document"
                @click="emit('delete', doc.id)"
              >
                <TrashIcon class="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.document-list {
  /* Component styles */
}
</style>
