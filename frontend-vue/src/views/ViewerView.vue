<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as documentsApi from '@/api/documents'
import type { Document } from '@/types'
import PdfViewer from '@/components/viewer/PdfViewer.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'

const route = useRoute()
const router = useRouter()

// State
const documents = ref<Document[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

// Parse route params
const documentId = computed(() => {
  const param = route.params.docId
  if (!param) return null
  const id = parseInt(param as string, 10)
  return isNaN(id) ? null : id
})

const pageNumber = computed(() => {
  const param = route.params.pageNum
  if (!param) return 1
  const num = parseInt(param as string, 10)
  return isNaN(num) || num < 1 ? 1 : num
})

// Load documents for the dropdown
async function loadDocuments() {
  loading.value = true
  error.value = null

  try {
    // Load up to 100 documents for the dropdown
    documents.value = await documentsApi.list(0, 100)
  } catch (err) {
    console.error('Failed to load documents:', err)
    error.value = 'Failed to load document list. Please try again.'
  } finally {
    loading.value = false
  }
}

// Handle document change from viewer
function handleDocumentChange(docId: number) {
  // Update URL without full page reload
  router.replace({
    name: 'viewer',
    params: { docId: docId.toString(), pageNum: '1' }
  })
}

// Handle page change from viewer
function handlePageChange(pageNum: number) {
  if (documentId.value) {
    router.replace({
      name: 'viewer',
      params: {
        docId: documentId.value.toString(),
        pageNum: pageNum.toString()
      }
    })
  }
}

// Handle viewer errors
function handleViewerError(message: string) {
  console.error('Viewer error:', message)
  // Could show a toast notification here
}

// Retry loading documents
function handleRetry() {
  loadDocuments()
}

// Load documents on mount
onMounted(() => {
  loadDocuments()
})
</script>

<template>
  <div class="viewer-view h-full flex flex-col">
    <!-- Loading state for document list -->
    <div
      v-if="loading"
      class="flex-1 flex items-center justify-center bg-gray-100"
    >
      <div class="text-center">
        <LoadingSpinner size="large" />
        <p class="mt-4 text-gray-600">Loading documents...</p>
      </div>
    </div>

    <!-- Error state -->
    <div
      v-else-if="error"
      class="flex-1 flex items-center justify-center bg-gray-100 p-4"
    >
      <div class="max-w-md w-full">
        <ErrorAlert :message="error" />
        <div class="mt-4 text-center">
          <button
            type="button"
            class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            @click="handleRetry"
          >
            Try Again
          </button>
        </div>
      </div>
    </div>

    <!-- No documents available -->
    <div
      v-else-if="documents.length === 0"
      class="flex-1 flex items-center justify-center bg-gray-100"
    >
      <div class="text-center">
        <svg class="mx-auto h-16 w-16 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <h3 class="mt-4 text-lg font-medium text-gray-900">No documents available</h3>
        <p class="mt-2 text-gray-500">Upload some PDF documents first to view them here.</p>
        <div class="mt-6">
          <router-link
            to="/upload"
            class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Upload Documents
          </router-link>
        </div>
      </div>
    </div>

    <!-- PDF Viewer -->
    <PdfViewer
      v-else
      :document-id="documentId"
      :page-number="pageNumber"
      :documents="documents"
      @document-change="handleDocumentChange"
      @page-change="handlePageChange"
      @error="handleViewerError"
    />
  </div>
</template>

<style scoped>
.viewer-view {
  /* Full height minus header if any */
  height: calc(100vh - 64px);
  min-height: 500px;
}
</style>
