import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import type { Document, UploadProgress } from '@/types'

export const useDocumentsStore = defineStore('documents', () => {
  // Document list
  const documents = ref<Document[]>([])
  const totalCount = ref(0)
  const loading = ref(false)

  // Upload progress tracking
  const uploads = reactive<Map<string, UploadProgress>>(new Map())

  // Computed
  const hasDocuments = computed(() => documents.value.length > 0)
  const activeUploads = computed(() =>
    Array.from(uploads.values()).filter(u => u.status === 'uploading' || u.status === 'processing')
  )

  // Actions
  function setDocuments(docs: Document[]) {
    documents.value = docs
  }

  function addDocument(doc: Document) {
    documents.value.unshift(doc)
    totalCount.value++
  }

  function updateDocument(doc: Document) {
    const index = documents.value.findIndex(d => d.id === doc.id)
    if (index !== -1) {
      documents.value[index] = doc
    }
  }

  function removeDocument(id: number) {
    const index = documents.value.findIndex(d => d.id === id)
    if (index !== -1) {
      documents.value.splice(index, 1)
      totalCount.value--
    }
  }

  function setTotalCount(count: number) {
    totalCount.value = count
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  // Upload tracking
  function startUpload(filename: string) {
    uploads.set(filename, {
      filename,
      progress: 0,
      status: 'pending'
    })
  }

  function updateUploadProgress(filename: string, progress: number, status?: UploadProgress['status']) {
    const upload = uploads.get(filename)
    if (upload) {
      upload.progress = progress
      if (status) upload.status = status
    }
  }

  function completeUpload(filename: string) {
    const upload = uploads.get(filename)
    if (upload) {
      upload.progress = 100
      upload.status = 'completed'
    }
  }

  function failUpload(filename: string, error: string) {
    const upload = uploads.get(filename)
    if (upload) {
      upload.status = 'error'
      upload.error = error
    }
  }

  function clearUpload(filename: string) {
    uploads.delete(filename)
  }

  function clearAllUploads() {
    uploads.clear()
  }

  return {
    documents,
    totalCount,
    loading,
    uploads,
    hasDocuments,
    activeUploads,
    setDocuments,
    addDocument,
    updateDocument,
    removeDocument,
    setTotalCount,
    setLoading,
    startUpload,
    updateUploadProgress,
    completeUpload,
    failUpload,
    clearUpload,
    clearAllUploads
  }
})
