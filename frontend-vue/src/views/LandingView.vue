<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  MagnifyingGlassIcon,
  PlusIcon,
  FolderIcon,
  DocumentTextIcon,
  CpuChipIcon,
} from '@heroicons/vue/24/outline'
import { useProjectsStore } from '@/stores/projects'
import * as documentsApi from '@/api/documents'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import ProjectCard from '@/components/projects/ProjectCard.vue'
import ProjectForm from '@/components/projects/ProjectForm.vue'

const router = useRouter()
const projectsStore = useProjectsStore()

// Local state
const searchQuery = ref('')
const showCreateModal = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const unassignedCount = ref(0)

// Computed
const filteredProjects = computed(() => {
  if (!searchQuery.value) {
    return projectsStore.projects
  }
  const query = searchQuery.value.toLowerCase()
  return projectsStore.projects.filter(
    p =>
      p.name.toLowerCase().includes(query) ||
      (p.description && p.description.toLowerCase().includes(query)) ||
      (p.facility_name && p.facility_name.toLowerCase().includes(query)) ||
      (p.system_type && p.system_type.toLowerCase().includes(query))
  )
})

const totalStats = computed(() => {
  const projects = projectsStore.projects
  return {
    projects: projects.length,
    documents: 0,
    equipment: 0,
  }
})

// Load projects and unassigned documents count
async function loadProjects() {
  loading.value = true
  error.value = null
  try {
    await projectsStore.fetchProjects()
    // Also load unassigned documents count
    const unassignedDocs = await documentsApi.listUnassigned()
    unassignedCount.value = unassignedDocs.length
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load projects'
  } finally {
    loading.value = false
  }
}

// Navigate to unassigned documents
function navigateToUnassigned() {
  router.push({ name: 'unassigned-documents' })
}

// Handle project creation
async function handleCreateProject(data: { name: string; description?: string | null; system_type?: string | null; facility_name?: string | null; status?: string; notes?: string | null; tags?: string[] }) {
  try {
    const project = await projectsStore.createProject(data)
    showCreateModal.value = false
    router.push({ name: 'project-dashboard', params: { id: project.id } })
  } catch (e) {
    throw e
  }
}

// Navigate to project
function navigateToProject(projectId: number) {
  router.push({ name: 'project-dashboard', params: { id: projectId } })
}

// Delete project
async function handleDeleteProject(projectId: number) {
  if (confirm('Are you sure you want to delete this project? This will delete all documents and data within it.')) {
    try {
      await projectsStore.deleteProject(projectId)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to delete project'
    }
  }
}

// Initialize
onMounted(() => {
  loadProjects()
})
</script>

<template>
  <div class="landing-view min-h-screen bg-gray-50">
    <!-- Hero Section -->
    <div class="bg-gradient-to-r from-blue-600 to-blue-800 text-white">
      <div class="container mx-auto px-4 py-12">
        <div class="max-w-4xl mx-auto text-center">
          <h1 class="text-4xl font-bold mb-4">
            Electrical Drawing RAG System
          </h1>
          <p class="text-xl text-blue-100 mb-8">
            Organize your electrical drawings into projects, extract equipment data,
            and query with AI-powered search.
          </p>

          <!-- Global Search Bar -->
          <div class="relative max-w-2xl mx-auto">
            <MagnifyingGlassIcon class="absolute left-4 top-1/2 -translate-y-1/2 h-6 w-6 text-gray-400" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search across all projects..."
              class="w-full pl-12 pr-4 py-4 text-lg text-gray-900 rounded-xl shadow-lg focus:ring-4 focus:ring-blue-300 focus:outline-none"
            />
          </div>
        </div>

        <!-- Stats Row -->
        <div class="max-w-3xl mx-auto mt-10 grid grid-cols-3 gap-6">
          <div class="bg-white/10 backdrop-blur rounded-lg p-4 text-center">
            <FolderIcon class="h-8 w-8 mx-auto mb-2 text-blue-200" />
            <div class="text-2xl font-bold">{{ totalStats.projects }}</div>
            <div class="text-sm text-blue-200">Projects</div>
          </div>
          <div class="bg-white/10 backdrop-blur rounded-lg p-4 text-center">
            <DocumentTextIcon class="h-8 w-8 mx-auto mb-2 text-blue-200" />
            <div class="text-2xl font-bold">{{ totalStats.documents }}</div>
            <div class="text-sm text-blue-200">Documents</div>
          </div>
          <div class="bg-white/10 backdrop-blur rounded-lg p-4 text-center">
            <CpuChipIcon class="h-8 w-8 mx-auto mb-2 text-blue-200" />
            <div class="text-2xl font-bold">{{ totalStats.equipment }}</div>
            <div class="text-sm text-blue-200">Equipment</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Unassigned Documents Banner -->
    <div v-if="unassignedCount > 0" class="container mx-auto px-4 pt-6">
      <div
        class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center justify-between cursor-pointer hover:bg-yellow-100 transition-colors"
        @click="navigateToUnassigned"
      >
        <div class="flex items-center">
          <DocumentTextIcon class="h-6 w-6 text-yellow-600 mr-3" />
          <div>
            <p class="font-medium text-yellow-800">
              {{ unassignedCount }} unassigned document{{ unassignedCount !== 1 ? 's' : '' }}
            </p>
            <p class="text-sm text-yellow-600">
              Click here to assign them to projects
            </p>
          </div>
        </div>
        <svg class="h-5 w-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>

    <!-- Projects Section -->
    <div class="container mx-auto px-4 py-8">
      <!-- Section Header -->
      <div class="flex justify-between items-center mb-6">
        <div>
          <h2 class="text-2xl font-bold text-gray-900">Your Projects</h2>
          <p class="text-gray-600">
            {{ filteredProjects.length }} project{{ filteredProjects.length !== 1 ? 's' : '' }}
          </p>
        </div>
        <button
          type="button"
          class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
          @click="showCreateModal = true"
        >
          <PlusIcon class="h-5 w-5 mr-2" />
          New Project
        </button>
      </div>

      <!-- Error State -->
      <ErrorAlert
        v-if="error"
        :message="error"
        :dismissable="true"
        class="mb-6"
        @dismiss="error = null"
      />

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-16">
        <LoadingSpinner size="large" text="Loading projects..." />
      </div>

      <!-- Empty State -->
      <div
        v-else-if="filteredProjects.length === 0"
        class="text-center py-16 bg-white rounded-lg border border-gray-200"
      >
        <FolderIcon class="h-16 w-16 mx-auto text-gray-300 mb-4" />
        <h3 class="text-lg font-medium text-gray-900 mb-2">
          {{ searchQuery ? 'No projects found' : 'No projects yet' }}
        </h3>
        <p class="text-gray-500 mb-6">
          {{ searchQuery
            ? 'Try adjusting your search query.'
            : 'Create your first project to get started.'
          }}
        </p>
        <button
          v-if="!searchQuery"
          type="button"
          class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          @click="showCreateModal = true"
        >
          <PlusIcon class="h-5 w-5 mr-2" />
          Create First Project
        </button>
      </div>

      <!-- Projects Grid -->
      <div
        v-else
        class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
      >
        <ProjectCard
          v-for="project in filteredProjects"
          :key="project.id"
          :project="project"
          @click="navigateToProject(project.id)"
          @delete="handleDeleteProject(project.id)"
        />
      </div>
    </div>

    <!-- Create Project Modal -->
    <ProjectForm
      v-if="showCreateModal"
      @submit="handleCreateProject"
      @cancel="showCreateModal = false"
    />
  </div>
</template>

<style scoped>
.landing-view {
  min-height: 100vh;
}
</style>
