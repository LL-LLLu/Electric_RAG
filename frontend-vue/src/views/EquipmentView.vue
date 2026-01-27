<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { MagnifyingGlassIcon, FunnelIcon, XMarkIcon, FolderIcon, DocumentTextIcon } from '@heroicons/vue/24/outline'
import { useEquipmentStore } from '@/stores/equipment'
import * as equipmentApi from '@/api/equipment'
import * as projectsApi from '@/api/projects'
import * as documentsApi from '@/api/documents'
import type { Equipment, EquipmentDetail, Project, Document } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import EquipmentCard from '@/components/equipment/EquipmentCard.vue'
import EquipmentDetailComponent from '@/components/equipment/EquipmentDetail.vue'

const equipmentStore = useEquipmentStore()

// Selection state
const projects = ref<Project[]>([])
const documents = ref<Document[]>([])
const selectedProjectId = ref<number | null>(null)
const selectedDocumentId = ref<number | null>(null)

// Local state
const searchInput = ref('')
const selectedType = ref('')
const loading = ref(false)
const loadingProjects = ref(false)
const loadingDocuments = ref(false)
const error = ref<string | null>(null)
const selectedEquipment = ref<EquipmentDetail | null>(null)
const loadingDetail = ref(false)
const detailError = ref<string | null>(null)

// Computed
const hasFilters = computed(() => searchInput.value !== '' || selectedType.value !== '')

const selectedProject = computed(() =>
  projects.value.find((p) => p.id === selectedProjectId.value)
)

const selectedDocument = computed(() =>
  documents.value.find((d) => d.id === selectedDocumentId.value)
)

const filteredEquipment = computed(() => {
  let result = equipmentStore.equipment

  // Filter by search query (local filtering)
  if (searchInput.value) {
    const query = searchInput.value.toLowerCase()
    result = result.filter(
      (e) =>
        e.tag.toLowerCase().includes(query) ||
        e.equipment_type.toLowerCase().includes(query) ||
        (e.description && e.description.toLowerCase().includes(query))
    )
  }

  // Filter by type
  if (selectedType.value) {
    result = result.filter((e) => e.equipment_type === selectedType.value)
  }

  return result
})

// Load projects on mount
async function loadProjects() {
  loadingProjects.value = true
  try {
    projects.value = await projectsApi.list()
  } catch (err) {
    console.error('Error loading projects:', err)
  } finally {
    loadingProjects.value = false
  }
}

// Load documents for selected project
async function loadDocuments() {
  if (!selectedProjectId.value) {
    documents.value = []
    return
  }

  loadingDocuments.value = true
  try {
    documents.value = await documentsApi.listByProject(selectedProjectId.value)
  } catch (err) {
    console.error('Error loading documents:', err)
  } finally {
    loadingDocuments.value = false
  }
}

// Load equipment for selected document
async function loadEquipment() {
  if (!selectedDocumentId.value) {
    equipmentStore.setEquipment([])
    equipmentStore.setTotalCount(0)
    return
  }

  loading.value = true
  error.value = null

  try {
    const equipment = await equipmentApi.listByDocument(selectedDocumentId.value, { limit: 500 })
    equipmentStore.setEquipment(equipment)
    equipmentStore.setTotalCount(equipment.length)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load equipment'
    console.error('Error loading equipment:', err)
  } finally {
    loading.value = false
  }
}

// Load equipment types for filter dropdown
async function loadEquipmentTypes() {
  try {
    const types = await equipmentApi.getTypes()
    equipmentStore.setAvailableTypes(types)
  } catch (err) {
    console.error('Error loading equipment types:', err)
  }
}

// Watch for project selection change
watch(selectedProjectId, () => {
  selectedDocumentId.value = null
  equipmentStore.setEquipment([])
  equipmentStore.setTotalCount(0)
  selectedEquipment.value = null
  loadDocuments()
})

// Watch for document selection change
watch(selectedDocumentId, () => {
  selectedEquipment.value = null
  loadEquipment()
})

// Handle equipment card click - load detail
async function handleEquipmentSelect(equipment: Equipment) {
  loadingDetail.value = true
  detailError.value = null

  try {
    const detail = await equipmentApi.getByTag(equipment.tag)
    selectedEquipment.value = detail
  } catch (err) {
    detailError.value = err instanceof Error ? err.message : 'Failed to load equipment details'
    console.error('Error loading equipment detail:', err)
  } finally {
    loadingDetail.value = false
  }
}

// Close detail view
function closeDetail() {
  selectedEquipment.value = null
  detailError.value = null
}

// Navigate to another equipment from relationship graph
async function handleNavigateToEquipment(tag: string) {
  loadingDetail.value = true
  detailError.value = null

  try {
    const detail = await equipmentApi.getByTag(tag)
    selectedEquipment.value = detail
  } catch (err) {
    detailError.value = err instanceof Error ? err.message : `Failed to load equipment ${tag}`
    console.error('Error loading equipment detail:', err)
  } finally {
    loadingDetail.value = false
  }
}

// Clear all filters
function clearFilters() {
  searchInput.value = ''
  selectedType.value = ''
}

// Handle dismiss error
function dismissError() {
  error.value = null
}

// Initialize on mount
onMounted(() => {
  loadProjects()
  loadEquipmentTypes()
})
</script>

<template>
  <div class="equipment-view min-h-screen bg-gray-50">
    <div class="container mx-auto px-4 py-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">Equipment Browser</h1>
        <p class="text-gray-600">
          Select a project and document to browse equipment.
        </p>
      </div>

      <!-- Project and Document Selection -->
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Project Selection -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              <FolderIcon class="h-4 w-4 inline mr-1" />
              Select Project
            </label>
            <select
              v-model="selectedProjectId"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              :disabled="loadingProjects"
            >
              <option :value="null">-- Select a project --</option>
              <option v-for="project in projects" :key="project.id" :value="project.id">
                {{ project.name }}
              </option>
            </select>
          </div>

          <!-- Document Selection -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              <DocumentTextIcon class="h-4 w-4 inline mr-1" />
              Select Document
            </label>
            <select
              v-model="selectedDocumentId"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              :disabled="!selectedProjectId || loadingDocuments"
            >
              <option :value="null">
                {{ !selectedProjectId ? '-- Select a project first --' : '-- Select a document --' }}
              </option>
              <option v-for="doc in documents" :key="doc.id" :value="doc.id">
                {{ doc.original_filename }} ({{ doc.page_count || 0 }} pages)
              </option>
            </select>
          </div>
        </div>

        <!-- Selected info -->
        <div v-if="selectedProject && selectedDocument" class="mt-4 p-3 bg-blue-50 rounded-lg">
          <p class="text-sm text-blue-800">
            <span class="font-medium">{{ selectedProject.name }}</span>
            &rarr;
            <span class="font-medium">{{ selectedDocument.original_filename }}</span>
            <span v-if="!loading" class="text-blue-600 ml-2">
              ({{ filteredEquipment.length }} equipment items)
            </span>
          </p>
        </div>
      </div>

      <!-- Search and Filter Bar (only shown when document is selected) -->
      <div
        v-if="selectedDocumentId"
        class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6"
      >
        <div class="flex flex-col sm:flex-row gap-4">
          <!-- Search Input -->
          <div class="flex-1 relative">
            <MagnifyingGlassIcon
              class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400"
            />
            <input
              v-model="searchInput"
              type="text"
              placeholder="Search by tag, type, or description..."
              class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
            />
          </div>

          <!-- Type Filter Dropdown -->
          <div class="relative sm:w-48">
            <FunnelIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <select
              v-model="selectedType"
              class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 appearance-none bg-white transition-colors"
            >
              <option value="">All Types</option>
              <option
                v-for="type in equipmentStore.availableTypes"
                :key="type"
                :value="type"
              >
                {{ type }}
              </option>
            </select>
          </div>

          <!-- Clear Filters Button -->
          <button
            v-if="hasFilters"
            type="button"
            class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
            @click="clearFilters"
          >
            <XMarkIcon class="h-4 w-4 mr-2" />
            Clear
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

      <!-- Empty State - No project/document selected -->
      <div
        v-if="!selectedDocumentId && !loading"
        class="text-center py-16 bg-white rounded-lg border border-gray-200"
      >
        <FolderIcon class="mx-auto h-16 w-16 text-gray-300 mb-4" />
        <h3 class="text-lg font-medium text-gray-900 mb-2">Select a project and document</h3>
        <p class="text-sm text-gray-500">
          Choose a project and document from the dropdowns above to view equipment.
        </p>
      </div>

      <!-- Loading State -->
      <div v-else-if="loading" class="flex justify-center py-16">
        <LoadingSpinner size="large" text="Loading equipment..." />
      </div>

      <!-- Main Content Area -->
      <div v-else class="flex flex-col lg:flex-row gap-6">
        <!-- Equipment Grid -->
        <div class="flex-1">
          <!-- Empty State - No equipment in document -->
          <div
            v-if="filteredEquipment.length === 0 && !loading"
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
                d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h3 class="mt-4 text-lg font-medium text-gray-900">No equipment found</h3>
            <p class="mt-2 text-sm text-gray-500">
              <template v-if="hasFilters">
                Try adjusting your search or filter criteria.
              </template>
              <template v-else>
                No equipment was extracted from this document.
              </template>
            </p>
            <button
              v-if="hasFilters"
              type="button"
              class="mt-4 inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
              @click="clearFilters"
            >
              Clear Filters
            </button>
          </div>

          <!-- Equipment Grid -->
          <div v-else class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            <EquipmentCard
              v-for="item in filteredEquipment"
              :key="item.id"
              :equipment="item"
              @select="handleEquipmentSelect"
            />
          </div>
        </div>

        <!-- Detail Panel (shown when equipment selected) -->
        <Transition
          enter-active-class="transition-all duration-300 ease-out"
          enter-from-class="opacity-0 translate-x-4"
          enter-to-class="opacity-100 translate-x-0"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 translate-x-0"
          leave-to-class="opacity-0 translate-x-4"
        >
          <div
            v-if="selectedEquipment || loadingDetail || detailError"
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

            <!-- Equipment Detail -->
            <EquipmentDetailComponent
              v-else-if="selectedEquipment"
              :equipment="selectedEquipment"
              @close="closeDetail"
              @navigate-to-equipment="handleNavigateToEquipment"
            />
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.equipment-view {
  min-height: 100vh;
}
</style>
