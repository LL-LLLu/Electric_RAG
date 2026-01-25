<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MagnifyingGlassIcon, XMarkIcon, ArrowPathIcon } from '@heroicons/vue/24/outline'
import { useDocumentsStore } from '@/stores/documents'
import * as documentsApi from '@/api/documents'
import type { Document, DocumentDetail } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import DocumentCard from '@/components/documents/DocumentCard.vue'
import DocumentDetailComponent from '@/components/documents/DocumentDetail.vue'

const documentsStore = useDocumentsStore()
const router = useRouter()

// Local state
const searchInput = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const selectedDocument = ref<DocumentDetail | null>(null)
const loadingDetail = ref(false)
const detailError = ref<string | null>(null)

// Computed
const hasSearch = computed(() => searchInput.value !== '')

const filteredDocuments = computed(() => {
  let result = documentsStore.documents

  // Filter by search query (local filtering on filename)
  if (searchInput.value) {
    const query = searchInput.value.toLowerCase()
    result = result.filter(d =>
      d.original_filename.toLowerCase().includes(query) ||
      d.filename.toLowerCase().includes(query)
    )
  }

  return result
})

// Load documents
async function loadDocuments() {
  loading.value = true
  error.value = null

  try {
    const docs = await documentsApi.list(0, 100)
    documentsStore.setDocuments(docs)
    documentsStore.setTotalCount(docs.length)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load documents'
    console.error('Error loading documents:', err)
  } finally {
    loading.value = false
  }
}

// Handle document card click - load detail
async function handleDocumentSelect(document: Document) {
  loadingDetail.value = true
  detailError.value = null

  try {
    const detail = await documentsApi.get(document.id)
    selectedDocument.value = detail
  } catch (err) {
    detailError.value = err instanceof Error ? err.message : 'Failed to load document details'
    console.error('Error loading document detail:', err)
  } finally {
    loadingDetail.value = false
  }
}

// Close detail view
function closeDetail() {
  selectedDocument.value = null
  detailError.value = null
}

// Clear search
function clearSearch() {
  searchInput.value = ''
}

// Handle dismiss error
function dismissError() {
  error.value = null
}

// Refresh documents list
async function refreshDocuments() {
  await loadDocuments()
}

// Navigate to upload page
function goToUpload() {
  router.push({ name: 'upload' })
}

// Initialize on mount
onMounted(() => {
  loadDocuments()
})
</script>

<template>
  <div class="documents-view min-h-screen bg-gray-50">
    <div class="container mx-auto px-4 py-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">Documents</h1>
        <p class="text-gray-600">
          Manage uploaded documents and view extracted content.
          <span v-if="!loading" class="text-blue-600 font-medium">
            {{ filteredDocuments.length }} of {{ documentsStore.totalCount }} documents
          </span>
        </p>
      </div>

      <!-- Search and Actions Bar -->
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
        <div class="flex flex-col sm:flex-row gap-4">
          <!-- Search Input -->
          <div class="flex-1 relative">
            <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              v-model="searchInput"
              type="text"
              placeholder="Search by filename..."
              class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
            />
          </div>

          <!-- Clear Search Button -->
          <button
            v-if="hasSearch"
            type="button"
            class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
            @click="clearSearch"
          >
            <XMarkIcon class="h-4 w-4 mr-2" />
            Clear
          </button>

          <!-- Refresh Button -->
          <button
            type="button"
            class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
            :disabled="loading"
            @click="refreshDocuments"
          >
            <ArrowPathIcon class="h-4 w-4 mr-2" :class="{ 'animate-spin': loading }" />
            Refresh
          </button>
        </div>
      </div>

      <!-- Error State -->
      <ErrorAlert
        v-if="error"
        :message="error"
        :dismissable="true"
        class="mb-6"
        @dismiss="dismissError"
      />

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-16">
        <LoadingSpinner size="large" text="Loading documents..." />
      </div>

      <!-- Main Content Area -->
      <div v-else class="flex flex-col lg:flex-row gap-6">
        <!-- Documents Grid -->
        <div class="flex-1">
          <!-- Empty State -->
          <div
            v-if="filteredDocuments.length === 0 && !loading"
            class="text-center py-16 bg-white rounded-lg border border-gray-200"
          >
            <svg
              class="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <h3 class="mt-4 text-lg font-medium text-gray-900">No documents found</h3>
            <p class="mt-2 text-sm text-gray-500">
              <template v-if="hasSearch">
                No documents match your search. Try a different search term.
              </template>
              <template v-else>
                Get started by uploading your first document.
              </template>
            </p>
            <div class="mt-6">
              <button
                v-if="hasSearch"
                type="button"
                class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
                @click="clearSearch"
              >
                Clear Search
              </button>
              <button
                v-else
                type="button"
                class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
                @click="goToUpload"
              >
                Upload Documents
              </button>
            </div>
          </div>

          <!-- Documents Grid -->
          <div
            v-else
            class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4"
          >
            <DocumentCard
              v-for="doc in filteredDocuments"
              :key="doc.id"
              :document="doc"
              @select="handleDocumentSelect"
            />
          </div>
        </div>

        <!-- Detail Panel (shown when document selected) -->
        <Transition
          enter-active-class="transition-all duration-300 ease-out"
          enter-from-class="opacity-0 translate-x-4"
          enter-to-class="opacity-100 translate-x-0"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 translate-x-0"
          leave-to-class="opacity-0 translate-x-4"
        >
          <div
            v-if="selectedDocument || loadingDetail || detailError"
            class="lg:w-96 xl:w-[450px] flex-shrink-0"
          >
            <!-- Loading Detail -->
            <div
              v-if="loadingDetail"
              class="bg-white rounded-lg shadow-lg border border-gray-200 p-8 flex justify-center"
            >
              <LoadingSpinner size="medium" text="Loading details..." />
            </div>

            <!-- Detail Error -->
            <div
              v-else-if="detailError"
              class="bg-white rounded-lg shadow-lg border border-gray-200 p-4"
            >
              <ErrorAlert :message="detailError" />
              <button
                type="button"
                class="mt-4 w-full inline-flex justify-center items-center px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
                @click="closeDetail"
              >
                Close
              </button>
            </div>

            <!-- Document Detail -->
            <DocumentDetailComponent
              v-else-if="selectedDocument"
              :document="selectedDocument"
              @close="closeDetail"
            />
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.documents-view {
  min-height: 100vh;
}
</style>
