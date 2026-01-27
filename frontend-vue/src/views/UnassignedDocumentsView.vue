<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeftIcon,
  ArrowsRightLeftIcon,
  TrashIcon,
  EyeIcon,
  ArrowPathIcon,
  DocumentTextIcon,
} from '@heroicons/vue/24/outline'
import * as documentsApi from '@/api/documents'
import * as projectsApi from '@/api/projects'
import type { Document, Project } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import DocumentCard from '@/components/documents/DocumentCard.vue'

const router = useRouter()

// State
const loading = ref(false)
const error = ref<string | null>(null)
const documents = ref<Document[]>([])
const showDeleteConfirm = ref(false)
const documentToDelete = ref<Document | null>(null)
const showMoveModal = ref(false)
const documentToMove = ref<Document | null>(null)
const allProjects = ref<Project[]>([])
const selectedTargetProject = ref<number | null>(null)
const moving = ref(false)

// Multi-select state
const selectedDocIds = ref<Set<number>>(new Set())
const showBulkDeleteConfirm = ref(false)
const showBulkMoveModal = ref(false)
const bulkOperating = ref(false)

// Computed
const hasSelection = computed(() => selectedDocIds.value.size > 0)
const allSelected = computed(() =>
  documents.value.length > 0 && selectedDocIds.value.size === documents.value.length
)
const selectedCount = computed(() => selectedDocIds.value.size)

// Selection functions
function toggleDocSelection(docId: number) {
  if (selectedDocIds.value.has(docId)) {
    selectedDocIds.value.delete(docId)
  } else {
    selectedDocIds.value.add(docId)
  }
  // Trigger reactivity
  selectedDocIds.value = new Set(selectedDocIds.value)
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedDocIds.value = new Set()
  } else {
    selectedDocIds.value = new Set(documents.value.map(d => d.id))
  }
}

function clearSelection() {
  selectedDocIds.value = new Set()
}

// Bulk operations
async function bulkAssign() {
  if (!selectedTargetProject.value || selectedDocIds.value.size === 0) return

  bulkOperating.value = true
  try {
    const result = await documentsApi.bulkAssign(
      Array.from(selectedDocIds.value),
      selectedTargetProject.value
    )

    showBulkMoveModal.value = false
    selectedTargetProject.value = null
    clearSelection()
    await loadData()

    if (result.failed_count > 0) {
      error.value = `${result.success_count} documents assigned, ${result.failed_count} failed`
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to assign documents'
  } finally {
    bulkOperating.value = false
  }
}

async function bulkDelete() {
  if (selectedDocIds.value.size === 0) return

  bulkOperating.value = true
  try {
    const result = await documentsApi.bulkDelete(Array.from(selectedDocIds.value))

    showBulkDeleteConfirm.value = false
    clearSelection()
    await loadData()

    if (result.failed_count > 0) {
      error.value = `${result.success_count} documents deleted, ${result.failed_count} failed`
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to delete documents'
  } finally {
    bulkOperating.value = false
  }
}

async function openBulkMoveModal() {
  try {
    allProjects.value = await projectsApi.list()
    selectedTargetProject.value = null
    showBulkMoveModal.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load projects'
  }
}

// Load unassigned documents
async function loadData() {
  loading.value = true
  error.value = null

  try {
    documents.value = await documentsApi.listUnassigned()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load documents'
  } finally {
    loading.value = false
  }
}

// Retry processing
async function retryDocument(doc: Document) {
  try {
    await documentsApi.retry(doc.id)
    await loadData()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to retry processing'
  }
}

// Delete document
function confirmDelete(doc: Document) {
  documentToDelete.value = doc
  showDeleteConfirm.value = true
}

async function deleteDocument() {
  if (!documentToDelete.value) return

  try {
    await documentsApi.deleteDocument(documentToDelete.value.id)
    showDeleteConfirm.value = false
    documentToDelete.value = null
    await loadData()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to delete document'
  }
}

// View in viewer
function viewDocument(doc: Document) {
  router.push({
    name: 'viewer',
    params: { docId: doc.id, pageNum: 1 },
  })
}

// Move document to a project
async function openMoveModal(doc: Document) {
  documentToMove.value = doc
  selectedTargetProject.value = null

  try {
    allProjects.value = await projectsApi.list()
    showMoveModal.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load projects'
  }
}

async function moveDocument() {
  if (!documentToMove.value || selectedTargetProject.value === null) return

  moving.value = true
  try {
    await documentsApi.assignToProject(documentToMove.value.id, {
      project_id: selectedTargetProject.value,
    })

    showMoveModal.value = false
    documentToMove.value = null
    selectedTargetProject.value = null

    // Reload documents list
    await loadData()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to move document'
  } finally {
    moving.value = false
  }
}

// Navigation
function goBack() {
  router.push({ name: 'landing' })
}

// Initialize
onMounted(() => {
  loadData()

  // Poll for updates while documents are processing
  const pollInterval = setInterval(async () => {
    const hasProcessing = documents.value.some((d) => d.processed === 0 || d.processed === 1)
    if (hasProcessing) {
      documents.value = await documentsApi.listUnassigned()
    }
  }, 5000)

  // Clean up
  return () => clearInterval(pollInterval)
})
</script>

<template>
  <div class="unassigned-documents min-h-screen bg-gray-50">
    <div class="container mx-auto px-4 py-8">
      <!-- Header -->
      <div class="mb-8">
        <button
          type="button"
          class="inline-flex items-center text-gray-600 hover:text-gray-900 mb-4"
          @click="goBack"
        >
          <ArrowLeftIcon class="h-5 w-5 mr-2" />
          Back to Projects
        </button>

        <div>
          <h1 class="text-3xl font-bold text-gray-900 mb-2">Unassigned Documents</h1>
          <p class="text-gray-600">
            Documents not yet assigned to any project. Assign them to a project to include them in
            project-scoped searches and chat.
          </p>
        </div>
      </div>

      <!-- Error Alert -->
      <ErrorAlert v-if="error" :message="error" class="mb-6" @dismiss="error = null" />

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-16">
        <LoadingSpinner size="large" text="Loading documents..." />
      </div>

      <!-- Empty State -->
      <div
        v-else-if="documents.length === 0"
        class="text-center py-16 bg-white rounded-lg border border-gray-200"
      >
        <DocumentTextIcon class="h-16 w-16 mx-auto text-gray-300 mb-4" />
        <h3 class="text-lg font-medium text-gray-900 mb-2">No unassigned documents</h3>
        <p class="text-gray-500">
          All documents have been assigned to projects. Great job!
        </p>
      </div>

      <!-- Bulk Actions Bar -->
      <div
        v-if="documents.length > 0"
        class="flex items-center justify-between mb-4 p-3 bg-white rounded-lg border border-gray-200"
      >
        <div class="flex items-center gap-3">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              :checked="allSelected"
              :indeterminate="hasSelection && !allSelected"
              class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              @change="toggleSelectAll"
            />
            <span class="text-sm text-gray-600">
              {{ allSelected ? 'Deselect all' : 'Select all' }}
            </span>
          </label>
          <span v-if="hasSelection" class="text-sm text-blue-600 font-medium">
            {{ selectedCount }} selected
          </span>
        </div>

        <div v-if="hasSelection" class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100"
            @click="openBulkMoveModal"
          >
            <ArrowsRightLeftIcon class="h-4 w-4 mr-1" />
            Assign to Project
          </button>
          <button
            type="button"
            class="inline-flex items-center px-3 py-1.5 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100"
            @click="showBulkDeleteConfirm = true"
          >
            <TrashIcon class="h-4 w-4 mr-1" />
            Delete
          </button>
          <button
            type="button"
            class="text-sm text-gray-500 hover:text-gray-700 ml-2"
            @click="clearSelection"
          >
            Clear
          </button>
        </div>
      </div>

      <!-- Documents Grid -->
      <div v-if="documents.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="doc in documents" :key="doc.id" class="relative">
          <!-- Selection checkbox -->
          <div class="absolute top-2 left-2 z-10">
            <label class="flex items-center cursor-pointer">
              <input
                type="checkbox"
                :checked="selectedDocIds.has(doc.id)"
                class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 bg-white shadow"
                @change="toggleDocSelection(doc.id)"
                @click.stop
              />
            </label>
          </div>

          <DocumentCard
            :document="doc"
            :class="{ 'ring-2 ring-blue-500': selectedDocIds.has(doc.id) }"
          />

          <!-- Action buttons overlay -->
          <div
            class="absolute top-2 right-2 flex gap-1 opacity-0 hover:opacity-100 transition-opacity"
          >
            <button
              v-if="doc.processed === 2"
              type="button"
              class="p-1.5 bg-white rounded-full shadow hover:bg-gray-100"
              title="View document"
              @click.stop="viewDocument(doc)"
            >
              <EyeIcon class="h-4 w-4 text-gray-600" />
            </button>
            <button
              type="button"
              class="p-1.5 bg-white rounded-full shadow hover:bg-blue-100"
              title="Assign to a project"
              @click.stop="openMoveModal(doc)"
            >
              <ArrowsRightLeftIcon class="h-4 w-4 text-blue-600" />
            </button>
            <button
              v-if="doc.processed === -1"
              type="button"
              class="p-1.5 bg-white rounded-full shadow hover:bg-gray-100"
              title="Retry processing"
              @click.stop="retryDocument(doc)"
            >
              <ArrowPathIcon class="h-4 w-4 text-gray-600" />
            </button>
            <button
              type="button"
              class="p-1.5 bg-white rounded-full shadow hover:bg-red-100"
              title="Delete document"
              @click.stop="confirmDelete(doc)"
            >
              <TrashIcon class="h-4 w-4 text-red-600" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div
      v-if="showDeleteConfirm"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Delete Document?</h3>
        <p class="text-gray-600 mb-4">
          Are you sure you want to delete "{{ documentToDelete?.original_filename }}"? This will
          remove all processed data and cannot be undone.
        </p>
        <div class="flex justify-end gap-3">
          <button
            type="button"
            class="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            @click="showDeleteConfirm = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-2 text-white bg-red-600 rounded-lg hover:bg-red-700"
            @click="deleteDocument"
          >
            Delete
          </button>
        </div>
      </div>
    </div>

    <!-- Assign to Project Modal (single) -->
    <div
      v-if="showMoveModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Assign to Project</h3>
        <p class="text-gray-600 mb-4">
          Assign "{{ documentToMove?.original_filename }}" to a project:
        </p>

        <select
          v-model="selectedTargetProject"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 mb-4"
        >
          <option :value="null" disabled>Select a project...</option>
          <option v-for="proj in allProjects" :key="proj.id" :value="proj.id">
            {{ proj.name }}
          </option>
        </select>

        <div class="flex justify-end gap-3">
          <button
            type="button"
            class="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            :disabled="moving"
            @click="showMoveModal = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            :disabled="selectedTargetProject === null || moving"
            @click="moveDocument"
          >
            {{ moving ? 'Assigning...' : 'Assign' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bulk Assign Modal -->
    <div
      v-if="showBulkMoveModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Bulk Assign to Project</h3>
        <p class="text-gray-600 mb-4">
          Assign {{ selectedCount }} selected documents to a project:
        </p>

        <select
          v-model="selectedTargetProject"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 mb-4"
        >
          <option :value="null" disabled>Select a project...</option>
          <option v-for="proj in allProjects" :key="proj.id" :value="proj.id">
            {{ proj.name }}
          </option>
        </select>

        <div class="flex justify-end gap-3">
          <button
            type="button"
            class="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            :disabled="bulkOperating"
            @click="showBulkMoveModal = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            :disabled="selectedTargetProject === null || bulkOperating"
            @click="bulkAssign"
          >
            {{ bulkOperating ? 'Assigning...' : `Assign ${selectedCount} Documents` }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bulk Delete Confirmation Modal -->
    <div
      v-if="showBulkDeleteConfirm"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Delete {{ selectedCount }} Documents?</h3>
        <p class="text-gray-600 mb-4">
          Are you sure you want to delete {{ selectedCount }} selected documents? This will
          remove all processed data and cannot be undone.
        </p>
        <div class="flex justify-end gap-3">
          <button
            type="button"
            class="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            :disabled="bulkOperating"
            @click="showBulkDeleteConfirm = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-2 text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
            :disabled="bulkOperating"
            @click="bulkDelete"
          >
            {{ bulkOperating ? 'Deleting...' : `Delete ${selectedCount} Documents` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
