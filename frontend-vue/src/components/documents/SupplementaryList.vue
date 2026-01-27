<template>
  <div class="supplementary-list">
    <!-- Upload Section -->
    <div class="upload-section mb-6">
      <div class="flex items-center gap-4">
        <label class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 transition-colors">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          <span>Upload Documents</span>
          <input
            type="file"
            class="hidden"
            accept=".xlsx,.xls,.csv,.docx"
            multiple
            @change="handleFileSelect"
          />
        </label>

        <select
          v-model="selectedCategory"
          class="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">Select Category (Optional)</option>
          <option value="IO_LIST">IO List</option>
          <option value="EQUIPMENT_SCHEDULE">Equipment Schedule</option>
          <option value="SEQUENCE_OF_OPERATION">Sequence of Operation</option>
          <option value="COMMISSIONING">Commissioning Guide</option>
          <option value="SUBMITTAL">Submittal</option>
          <option value="OTHER">Other</option>
        </select>
      </div>

      <p v-if="uploadError" class="mt-2 text-red-600 text-sm">{{ uploadError }}</p>
      <p v-if="uploading" class="mt-2 text-blue-600 text-sm">
        Uploading {{ uploadProgress.current }} of {{ uploadProgress.total }}...
      </p>
    </div>

    <!-- Documents Grid -->
    <div v-if="loading" class="text-center py-8 text-gray-500">
      Loading documents...
    </div>

    <div v-else-if="documents.length === 0" class="text-center py-8 text-gray-500">
      No supplementary documents yet. Upload Excel or Word files to enhance search results.
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
      >
        <!-- Document Header -->
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-2">
            <span class="text-2xl">{{ getDocumentIcon(doc.document_type) }}</span>
            <div>
              <h3 class="font-medium text-gray-900 truncate max-w-[200px]" :title="doc.original_filename">
                {{ doc.original_filename }}
              </h3>
              <p class="text-xs text-gray-500">
                {{ formatFileSize(doc.file_size) }}
              </p>
            </div>
          </div>

          <!-- Status Badge -->
          <span :class="getStatusClass(doc.processed)">
            {{ getStatusText(doc.processed) }}
          </span>
        </div>

        <!-- Category -->
        <div v-if="doc.content_category" class="mt-2">
          <span class="inline-block px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded">
            {{ formatCategory(doc.content_category) }}
          </span>
        </div>

        <!-- Error Message -->
        <p v-if="doc.processing_error" class="mt-2 text-xs text-red-600">
          Error: {{ doc.processing_error }}
        </p>

        <!-- Actions -->
        <div class="mt-4 flex items-center gap-2">
          <button
            v-if="doc.processed === -1"
            @click="handleReprocess(doc.id)"
            class="text-sm text-blue-600 hover:text-blue-800"
            :disabled="reprocessing === doc.id"
          >
            {{ reprocessing === doc.id ? 'Reprocessing...' : 'Retry' }}
          </button>

          <button
            @click="confirmDelete(doc)"
            class="text-sm text-red-600 hover:text-red-800 ml-auto"
          >
            Delete
          </button>
        </div>

        <!-- Upload Date -->
        <p class="mt-2 text-xs text-gray-400">
          Uploaded {{ formatDate(doc.created_at) }}
        </p>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="deleteTarget" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg p-6 max-w-sm mx-4">
        <h3 class="text-lg font-semibold text-gray-900">Delete Document</h3>
        <p class="mt-2 text-gray-600">
          Are you sure you want to delete "{{ deleteTarget.original_filename }}"? This action cannot be undone.
        </p>
        <div class="mt-4 flex justify-end gap-3">
          <button
            @click="deleteTarget = null"
            class="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>
          <button
            @click="handleDelete"
            class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            :disabled="deleting"
          >
            {{ deleting ? 'Deleting...' : 'Delete' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  uploadSupplementary,
  getSupplementaryDocuments,
  deleteSupplementary,
  reprocessSupplementary,
  type SupplementaryDocument,
  type ContentCategory
} from '@/api/supplementary'

const props = defineProps<{
  projectId: number
}>()

const emit = defineEmits<{
  (e: 'document-uploaded', doc: SupplementaryDocument): void
  (e: 'document-deleted', id: number): void
}>()

// State
const documents = ref<SupplementaryDocument[]>([])
const loading = ref(true)
const uploading = ref(false)
const uploadProgress = ref({ current: 0, total: 0 })
const uploadError = ref('')
const selectedCategory = ref<ContentCategory | ''>('')
const deleteTarget = ref<SupplementaryDocument | null>(null)
const deleting = ref(false)
const reprocessing = ref<number | null>(null)

// Load documents
async function loadDocuments() {
  loading.value = true
  try {
    documents.value = await getSupplementaryDocuments(props.projectId)
  } catch (err) {
    console.error('Failed to load supplementary documents:', err)
  } finally {
    loading.value = false
  }
}

// Handle file selection (supports multiple files)
async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return

  uploadError.value = ''
  uploading.value = true
  uploadProgress.value = { current: 0, total: files.length }

  const category = selectedCategory.value || undefined
  const errors: string[] = []

  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    if (!file) continue

    uploadProgress.value.current = i + 1

    try {
      const doc = await uploadSupplementary(props.projectId, file, category)
      documents.value.unshift(doc)
      emit('document-uploaded', doc)
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to upload'
      errors.push(`${file.name}: ${errorMsg}`)
      console.error(`Upload failed for ${file.name}:`, err)
    }
  }

  if (errors.length > 0) {
    uploadError.value = errors.length === 1
      ? (errors[0] ?? 'Upload failed')
      : `${errors.length} files failed to upload`
  } else {
    uploadError.value = ''
  }

  selectedCategory.value = ''
  uploading.value = false
  input.value = '' // Reset file input
}

// Confirm delete
function confirmDelete(doc: SupplementaryDocument) {
  deleteTarget.value = doc
}

// Handle delete
async function handleDelete() {
  if (!deleteTarget.value) return

  deleting.value = true
  try {
    await deleteSupplementary(deleteTarget.value.id)
    documents.value = documents.value.filter(d => d.id !== deleteTarget.value!.id)
    emit('document-deleted', deleteTarget.value.id)
    deleteTarget.value = null
  } catch (err) {
    console.error('Failed to delete document:', err)
  } finally {
    deleting.value = false
  }
}

// Handle reprocess
async function handleReprocess(docId: number) {
  reprocessing.value = docId
  try {
    await reprocessSupplementary(docId)
    // Update status locally
    const doc = documents.value.find(d => d.id === docId)
    if (doc) {
      doc.processed = 0
      doc.processing_error = null
    }
  } catch (err) {
    console.error('Failed to reprocess document:', err)
  } finally {
    reprocessing.value = null
  }
}

// Helpers
function getDocumentIcon(type: string): string {
  return type === 'EXCEL' ? '📊' : '📝'
}

function getStatusText(status: number): string {
  switch (status) {
    case 0: return 'Pending'
    case 1: return 'Processing'
    case 2: return 'Done'
    case -1: return 'Error'
    default: return 'Unknown'
  }
}

function getStatusClass(status: number): string {
  const base = 'px-2 py-1 text-xs rounded-full'
  switch (status) {
    case 0: return `${base} bg-yellow-100 text-yellow-800`
    case 1: return `${base} bg-blue-100 text-blue-800`
    case 2: return `${base} bg-green-100 text-green-800`
    case -1: return `${base} bg-red-100 text-red-800`
    default: return `${base} bg-gray-100 text-gray-800`
  }
}

function formatCategory(category: string): string {
  return category.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return 'Unknown size'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

// Load on mount
onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
.supplementary-list {
  padding: 1rem;
}
</style>
