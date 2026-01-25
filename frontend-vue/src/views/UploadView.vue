<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useIntervalFn } from '@vueuse/core'
import { useDocumentsStore } from '@/stores/documents'
import * as documentsApi from '@/api/documents'
import FileUploader from '@/components/upload/FileUploader.vue'
import UploadProgress from '@/components/upload/UploadProgress.vue'
import DocumentList from '@/components/upload/DocumentList.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'

const router = useRouter()
const documentsStore = useDocumentsStore()

const error = ref<string | null>(null)
const loadingDocuments = ref(false)

// Load documents on mount
onMounted(async () => {
  await loadDocuments()
})

// Poll for document status updates every 5 seconds
const { pause } = useIntervalFn(async () => {
  // Only poll if there are pending or processing documents
  const hasPendingDocs = documentsStore.documents.some(
    doc => doc.processed === 0 || doc.processed === 1
  )
  const hasActiveUploads = documentsStore.activeUploads.length > 0

  if (hasPendingDocs || hasActiveUploads) {
    await loadDocuments()
  }
}, 5000)

// Clean up on unmount
onUnmounted(() => {
  pause()
})

async function loadDocuments() {
  loadingDocuments.value = true
  try {
    const docs = await documentsApi.list(0, 20)
    documentsStore.setDocuments(docs)
  } catch (err: any) {
    console.error('Failed to load documents:', err)
    error.value = err.response?.data?.detail || err.message || 'Failed to load documents'
  } finally {
    loadingDocuments.value = false
  }
}

async function handleUpload(file: File) {
  // Start tracking the upload
  documentsStore.startUpload(file.name)
  documentsStore.updateUploadProgress(file.name, 0, 'uploading')

  try {
    // Upload with progress callback
    await documentsApi.upload(file, (percent) => {
      documentsStore.updateUploadProgress(file.name, percent, 'uploading')
    })

    // Mark as processing (backend is now processing the document)
    documentsStore.updateUploadProgress(file.name, 100, 'processing')

    // Refresh document list to show new document
    await loadDocuments()

    // Mark upload as complete after a short delay
    setTimeout(() => {
      documentsStore.completeUpload(file.name)
      // Clear completed upload after 3 seconds
      setTimeout(() => {
        documentsStore.clearUpload(file.name)
      }, 3000)
    }, 1000)
  } catch (err: any) {
    console.error('Upload failed:', err)
    const errorMessage = err.response?.data?.detail || err.message || 'Upload failed'
    documentsStore.failUpload(file.name, errorMessage)
    error.value = `Failed to upload ${file.name}: ${errorMessage}`
  }
}

async function handleRetry(id: number) {
  try {
    await documentsApi.retry(id)
    // Refresh document list to show updated status
    await loadDocuments()
  } catch (err: any) {
    console.error('Retry failed:', err)
    error.value = err.response?.data?.detail || err.message || 'Failed to retry processing'
  }
}

async function handleDelete(id: number) {
  if (!confirm('Are you sure you want to delete this document?')) {
    return
  }

  try {
    await documentsApi.deleteDocument(id)
    documentsStore.removeDocument(id)
  } catch (err: any) {
    console.error('Delete failed:', err)
    error.value = err.response?.data?.detail || err.message || 'Failed to delete document'
  }
}

function handleView(id: number) {
  router.push({ name: 'viewer', params: { id } })
}

function dismissError() {
  error.value = null
}
</script>

<template>
  <div class="upload-view">
    <div class="container mx-auto px-4 py-8 max-w-4xl">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">Upload Documents</h1>
        <p class="text-gray-600">
          Upload PDF documents for processing and equipment extraction.
        </p>
      </div>

      <!-- Error Alert -->
      <div v-if="error" class="mb-6">
        <ErrorAlert
          :message="error"
          :dismissable="true"
          @dismiss="dismissError"
        />
      </div>

      <!-- File Uploader -->
      <div class="mb-8">
        <FileUploader @upload="handleUpload" />
      </div>

      <!-- Upload Progress -->
      <div v-if="documentsStore.uploads.size > 0" class="mb-8">
        <UploadProgress :uploads="documentsStore.uploads" />
      </div>

      <!-- Recent Documents -->
      <DocumentList
        :documents="documentsStore.documents"
        :loading="loadingDocuments && documentsStore.documents.length === 0"
        @retry="handleRetry"
        @delete="handleDelete"
        @view="handleView"
      />
    </div>
  </div>
</template>

<style scoped>
.upload-view {
  min-height: 100vh;
  background-color: #f9fafb;
}
</style>
