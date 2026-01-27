<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeftIcon,
  CloudArrowUpIcon,
  ArrowPathIcon,
  TrashIcon,
  EyeIcon,
  ArrowsRightLeftIcon,
  PlusIcon,
} from '@heroicons/vue/24/outline'
import { useProjectsStore } from '@/stores/projects'
import * as documentsApi from '@/api/documents'
import * as projectsApi from '@/api/projects'
import { getSupplementaryDocuments } from '@/api/supplementary'
import type { Document, Project } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import DocumentCard from '@/components/documents/DocumentCard.vue'
import SupplementaryList from '@/components/documents/SupplementaryList.vue'

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()

// Tab navigation
type TabType = 'drawings' | 'supplementary'
const activeTab = ref<TabType>('drawings')
const supplementaryCount = ref(0)

// State
const loading = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const error = ref<string | null>(null)
const documents = ref<Document[]>([])
const selectedDocument = ref<Document | null>(null)
const showDeleteConfirm = ref(false)
const documentToDelete = ref<Document | null>(null)
const showMoveModal = ref(false)
const documentToMove = ref<Document | null>(null)
const allProjects = ref<Project[]>([])
const selectedTargetProject = ref<number | null>(null)
const moving = ref(false)
const showAddExistingModal = ref(false)
const unassignedDocuments = ref<Document[]>([])
const selectedDocumentsToAdd = ref<number[]>([])
const addingDocuments = ref(false)

// Computed
const projectId = computed(() => Number(route.params.id))
const project = computed(() => projectsStore.currentProject)
const drawingsCount = computed(() => documents.value.length)

// File input ref
const fileInputRef = ref<HTMLInputElement | null>(null)

// Load project and documents
async function loadData() {
  loading.value = true
  error.value = null

  try {
    if (!project.value || project.value.id !== projectId.value) {
      await projectsStore.fetchProject(projectId.value)
    }
    documents.value = await documentsApi.listByProject(projectId.value)
    // Load supplementary count for tab label
    await loadSupplementaryCount()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load documents'
  } finally {
    loading.value = false
  }
}

// Load supplementary documents count
async function loadSupplementaryCount() {
  try {
    const suppDocs = await getSupplementaryDocuments(projectId.value)
    supplementaryCount.value = suppDocs.length
  } catch (e) {
    console.error('Failed to load supplementary count:', e)
    supplementaryCount.value = 0
  }
}

// Handle supplementary document events
function handleSupplementaryUploaded() {
  supplementaryCount.value++
}

function handleSupplementaryDeleted() {
  supplementaryCount.value = Math.max(0, supplementaryCount.value - 1)
}

// Upload document
function triggerUpload() {
  fileInputRef.value?.click()
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.pdf')) {
    error.value = 'Only PDF files are supported'
    return
  }

  uploading.value = true
  uploadProgress.value = 0
  error.value = null

  try {
    // Use the project-scoped upload endpoint
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(
      `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/documents/project/${projectId.value}/upload`,
      {
        method: 'POST',
        body: formData,
      }
    )

    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Upload failed')
    }

    // Refresh documents list
    await loadData()

    // Refresh project stats
    await projectsStore.fetchProject(projectId.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to upload document'
  } finally {
    uploading.value = false
    uploadProgress.value = 0
    // Reset input
    if (input) input.value = ''
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

    // Refresh project stats
    await projectsStore.fetchProject(projectId.value)
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

// Move document to another project
async function openMoveModal(doc: Document) {
  documentToMove.value = doc
  selectedTargetProject.value = null

  try {
    // Load all projects to show in dropdown
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

    // Reload documents list (document was moved out of this project)
    await loadData()

    // Refresh project stats
    await projectsStore.fetchProject(projectId.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to move document'
  } finally {
    moving.value = false
  }
}

// Select document for detail view
function selectDocument(doc: Document) {
  selectedDocument.value = selectedDocument.value?.id === doc.id ? null : doc
}

// Add existing unassigned documents to this project
async function openAddExistingModal() {
  selectedDocumentsToAdd.value = []

  try {
    unassignedDocuments.value = await documentsApi.listUnassigned()
    if (unassignedDocuments.value.length === 0) {
      error.value = 'No unassigned documents available to add'
      return
    }
    showAddExistingModal.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load unassigned documents'
  }
}

function toggleDocumentSelection(docId: number) {
  const index = selectedDocumentsToAdd.value.indexOf(docId)
  if (index === -1) {
    selectedDocumentsToAdd.value.push(docId)
  } else {
    selectedDocumentsToAdd.value.splice(index, 1)
  }
}

async function addSelectedDocuments() {
  if (selectedDocumentsToAdd.value.length === 0) return

  addingDocuments.value = true
  try {
    // Assign each selected document to this project
    await Promise.all(
      selectedDocumentsToAdd.value.map((docId) =>
        documentsApi.assignToProject(docId, { project_id: projectId.value })
      )
    )

    showAddExistingModal.value = false
    selectedDocumentsToAdd.value = []

    // Reload documents list
    await loadData()

    // Refresh project stats
    await projectsStore.fetchProject(projectId.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to add documents'
  } finally {
    addingDocuments.value = false
  }
}

// Navigation
function goBack() {
  router.push({ name: 'project-dashboard', params: { id: projectId.value } })
}

// Initialize
onMounted(() => {
  loadData()

  // Poll for updates while documents are processing
  const pollInterval = setInterval(async () => {
    const hasProcessing = documents.value.some((d) => d.processed === 0 || d.processed === 1)
    if (hasProcessing) {
      documents.value = await documentsApi.listByProject(projectId.value)
    }
  }, 5000)

  // Clean up
  return () => clearInterval(pollInterval)
})
</script>

<template>
  <div class="project-documents min-h-screen bg-gray-50">
    <div class="container mx-auto px-4 py-8">
      <!-- Header -->
      <div class="mb-8">
        <button
          type="button"
          class="inline-flex items-center text-gray-600 hover:text-gray-900 mb-4"
          @click="goBack"
        >
          <ArrowLeftIcon class="h-5 w-5 mr-2" />
          Back to Project
        </button>

        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-3xl font-bold text-gray-900 mb-2">Documents</h1>
            <p v-if="project" class="text-gray-600">
              Manage documents for {{ project.name }}
            </p>
          </div>
          <!-- Upload buttons for Drawings tab only -->
          <div v-if="activeTab === 'drawings'" class="flex gap-2">
            <button
              type="button"
              class="inline-flex items-center px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              @click="openAddExistingModal"
            >
              <PlusIcon class="h-5 w-5 mr-2" />
              Add Existing
            </button>
            <button
              type="button"
              class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              :disabled="uploading"
              @click="triggerUpload"
            >
              <CloudArrowUpIcon v-if="!uploading" class="h-5 w-5 mr-2" />
              <LoadingSpinner v-else size="small" class="mr-2" />
              {{ uploading ? 'Uploading...' : 'Upload Document' }}
            </button>
          </div>
          <input
            ref="fileInputRef"
            type="file"
            accept=".pdf"
            class="hidden"
            @change="handleFileSelect"
          />
        </div>

        <!-- Tab Navigation -->
        <div class="mt-6 border-b border-gray-200">
          <nav class="-mb-px flex space-x-8" aria-label="Tabs">
            <button
              type="button"
              :class="[
                activeTab === 'drawings'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm'
              ]"
              @click="activeTab = 'drawings'"
            >
              Drawings ({{ drawingsCount }})
            </button>
            <button
              type="button"
              :class="[
                activeTab === 'supplementary'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm'
              ]"
              @click="activeTab = 'supplementary'"
            >
              Supplementary ({{ supplementaryCount }})
            </button>
          </nav>
        </div>
      </div>

      <!-- Error Alert -->
      <ErrorAlert v-if="error" :message="error" class="mb-6" @dismiss="error = null" />

      <!-- Drawings Tab Content -->
      <div v-if="activeTab === 'drawings'">
        <!-- Loading State -->
        <div v-if="loading" class="flex justify-center py-16">
          <LoadingSpinner size="large" text="Loading documents..." />
        </div>

        <!-- Empty State -->
        <div
          v-else-if="documents.length === 0"
          class="text-center py-16 bg-white rounded-lg border border-gray-200"
        >
          <CloudArrowUpIcon class="h-16 w-16 mx-auto text-gray-300 mb-4" />
          <h3 class="text-lg font-medium text-gray-900 mb-2">No drawings yet</h3>
          <p class="text-gray-500 mb-4">
            Upload electrical drawings (PDF) to start analyzing them.
          </p>
          <button
            type="button"
            class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            @click="triggerUpload"
          >
            <CloudArrowUpIcon class="h-5 w-5 mr-2" />
            Upload Your First Drawing
          </button>
        </div>

        <!-- Documents Grid -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="doc in documents"
            :key="doc.id"
            class="relative"
          >
            <DocumentCard
              :document="doc"
              @select="selectDocument"
            />

            <!-- Action buttons overlay -->
            <div class="absolute top-2 right-2 flex gap-1 opacity-0 hover:opacity-100 transition-opacity">
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
                class="p-1.5 bg-white rounded-full shadow hover:bg-gray-100"
                title="Move to another project"
                @click.stop="openMoveModal(doc)"
              >
                <ArrowsRightLeftIcon class="h-4 w-4 text-gray-600" />
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

      <!-- Supplementary Tab Content -->
      <div v-else-if="activeTab === 'supplementary'">
        <SupplementaryList
          :project-id="projectId"
          @document-uploaded="handleSupplementaryUploaded"
          @document-deleted="handleSupplementaryDeleted"
        />
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

    <!-- Move Document Modal -->
    <div
      v-if="showMoveModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Move Document</h3>
        <p class="text-gray-600 mb-4">
          Move "{{ documentToMove?.original_filename }}" to another project:
        </p>

        <select
          v-model="selectedTargetProject"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 mb-4"
        >
          <option :value="null" disabled>Select a project...</option>
          <option
            v-for="proj in allProjects.filter((p) => p.id !== projectId)"
            :key="proj.id"
            :value="proj.id"
          >
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
            {{ moving ? 'Moving...' : 'Move' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Add Existing Documents Modal -->
    <div
      v-if="showAddExistingModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div class="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6 max-h-[80vh] flex flex-col">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Add Existing Documents</h3>
        <p class="text-gray-600 mb-4">
          Select documents to add to this project:
        </p>

        <!-- Document list with checkboxes -->
        <div class="flex-1 overflow-y-auto border border-gray-200 rounded-lg mb-4 min-h-[200px]">
          <div
            v-for="doc in unassignedDocuments"
            :key="doc.id"
            class="flex items-center px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-b-0 cursor-pointer"
            @click="toggleDocumentSelection(doc.id)"
          >
            <input
              type="checkbox"
              :checked="selectedDocumentsToAdd.includes(doc.id)"
              class="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
              @click.stop="toggleDocumentSelection(doc.id)"
            />
            <div class="ml-3 flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-900 truncate">
                {{ doc.original_filename }}
              </p>
              <p class="text-xs text-gray-500">
                {{ doc.page_count || 0 }} pages
                <span v-if="doc.processed === 2" class="text-green-600 ml-2">Processed</span>
                <span v-else-if="doc.processed === 1" class="text-yellow-600 ml-2">Processing...</span>
                <span v-else-if="doc.processed === -1" class="text-red-600 ml-2">Error</span>
                <span v-else class="text-gray-400 ml-2">Pending</span>
              </p>
            </div>
          </div>
        </div>

        <div class="flex justify-between items-center">
          <span class="text-sm text-gray-500">
            {{ selectedDocumentsToAdd.length }} document{{ selectedDocumentsToAdd.length !== 1 ? 's' : '' }} selected
          </span>
          <div class="flex gap-3">
            <button
              type="button"
              class="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              :disabled="addingDocuments"
              @click="showAddExistingModal = false"
            >
              Cancel
            </button>
            <button
              type="button"
              class="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              :disabled="selectedDocumentsToAdd.length === 0 || addingDocuments"
              @click="addSelectedDocuments"
            >
              {{ addingDocuments ? 'Adding...' : 'Add Selected' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
