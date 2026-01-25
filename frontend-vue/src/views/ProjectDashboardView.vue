<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  DocumentTextIcon,
  CpuChipIcon,
  ChatBubbleLeftRightIcon,
  DocumentDuplicateIcon,
  ArrowLeftIcon,
  PlusIcon,
  PencilIcon,
} from '@heroicons/vue/24/outline'
import { useProjectsStore } from '@/stores/projects'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import ProjectForm from '@/components/projects/ProjectForm.vue'
import type { ProjectUpdate } from '@/types'

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()

// State
const loading = ref(false)
const error = ref<string | null>(null)
const showEditModal = ref(false)

// Computed
const projectId = computed(() => Number(route.params.id))
const project = computed(() => projectsStore.currentProject)

// Load project
async function loadProject() {
  loading.value = true
  error.value = null
  try {
    await projectsStore.fetchProject(projectId.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load project'
  } finally {
    loading.value = false
  }
}

// Handle edit
async function handleEditProject(data: ProjectUpdate) {
  try {
    await projectsStore.updateProject(projectId.value, data)
    showEditModal.value = false
    await loadProject()
  } catch (e) {
    throw e
  }
}

// Navigate to documents
function goToDocuments() {
  router.push({ name: 'project-documents', params: { id: projectId.value } })
}

// Navigate to conversations
function goToConversations() {
  router.push({ name: 'project-conversations', params: { id: projectId.value } })
}

// Navigate to new chat
function startNewChat() {
  router.push({ name: 'project-chat', params: { id: projectId.value } })
}

// Navigate back
function goBack() {
  router.push({ name: 'home' })
}

// Watch for route changes
watch(() => route.params.id, () => {
  if (route.params.id) {
    loadProject()
  }
})

// Initialize
onMounted(() => {
  loadProject()
})
</script>

<template>
  <div class="project-dashboard min-h-screen bg-gray-50">
    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center min-h-screen">
      <LoadingSpinner size="large" text="Loading project..." />
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="container mx-auto px-4 py-8">
      <ErrorAlert :message="error" />
      <button
        type="button"
        class="mt-4 inline-flex items-center px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
        @click="goBack"
      >
        <ArrowLeftIcon class="h-5 w-5 mr-2" />
        Back to Projects
      </button>
    </div>

    <!-- Project Content -->
    <div v-else-if="project" class="container mx-auto px-4 py-8">
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

        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-3xl font-bold text-gray-900 mb-2">
              {{ project.name }}
            </h1>
            <p v-if="project.description" class="text-gray-600 max-w-2xl">
              {{ project.description }}
            </p>

            <!-- Metadata -->
            <div class="flex flex-wrap gap-2 mt-3">
              <span
                v-if="project.facility_name"
                class="text-sm bg-gray-100 text-gray-700 px-3 py-1 rounded-full"
              >
                {{ project.facility_name }}
              </span>
              <span
                v-if="project.system_type"
                class="text-sm bg-blue-100 text-blue-700 px-3 py-1 rounded-full"
              >
                {{ project.system_type }}
              </span>
              <span
                :class="[
                  'text-sm px-3 py-1 rounded-full',
                  project.status === 'active' ? 'bg-green-100 text-green-700' :
                  project.status === 'completed' ? 'bg-blue-100 text-blue-700' :
                  'bg-gray-100 text-gray-700'
                ]"
              >
                {{ project.status }}
              </span>
            </div>
          </div>

          <button
            type="button"
            class="inline-flex items-center px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
            @click="showEditModal = true"
          >
            <PencilIcon class="h-5 w-5 mr-2" />
            Edit
          </button>
        </div>
      </div>

      <!-- Stats Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div class="flex items-center">
            <div class="p-3 bg-blue-100 rounded-lg">
              <DocumentTextIcon class="h-6 w-6 text-blue-600" />
            </div>
            <div class="ml-4">
              <p class="text-sm text-gray-500">Documents</p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ project.stats.document_count }}
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div class="flex items-center">
            <div class="p-3 bg-green-100 rounded-lg">
              <DocumentDuplicateIcon class="h-6 w-6 text-green-600" />
            </div>
            <div class="ml-4">
              <p class="text-sm text-gray-500">Pages</p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ project.stats.page_count }}
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div class="flex items-center">
            <div class="p-3 bg-purple-100 rounded-lg">
              <CpuChipIcon class="h-6 w-6 text-purple-600" />
            </div>
            <div class="ml-4">
              <p class="text-sm text-gray-500">Equipment</p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ project.stats.equipment_count }}
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div class="flex items-center">
            <div class="p-3 bg-orange-100 rounded-lg">
              <ChatBubbleLeftRightIcon class="h-6 w-6 text-orange-600" />
            </div>
            <div class="ml-4">
              <p class="text-sm text-gray-500">Conversations</p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ project.stats.conversation_count }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- Documents Section -->
        <div
          class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:border-blue-300 hover:shadow-md transition-all cursor-pointer"
          @click="goToDocuments"
        >
          <div class="flex items-center mb-4">
            <DocumentTextIcon class="h-8 w-8 text-blue-600" />
            <h3 class="ml-3 text-lg font-semibold text-gray-900">Documents</h3>
          </div>
          <p class="text-gray-600 mb-4">
            Upload and manage electrical drawings for this project.
          </p>
          <div class="flex items-center text-blue-600 font-medium">
            Manage Documents
            <svg class="ml-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>

        <!-- Conversations Section -->
        <div
          class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:border-blue-300 hover:shadow-md transition-all cursor-pointer"
          @click="goToConversations"
        >
          <div class="flex items-center mb-4">
            <ChatBubbleLeftRightIcon class="h-8 w-8 text-orange-600" />
            <h3 class="ml-3 text-lg font-semibold text-gray-900">Conversations</h3>
          </div>
          <p class="text-gray-600 mb-4">
            View previous chat sessions and search history.
          </p>
          <div class="flex items-center text-blue-600 font-medium">
            View Conversations
            <svg class="ml-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>

        <!-- New Chat Section -->
        <div
          class="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg shadow-sm p-6 hover:shadow-md transition-all cursor-pointer text-white"
          @click="startNewChat"
        >
          <div class="flex items-center mb-4">
            <PlusIcon class="h-8 w-8" />
            <h3 class="ml-3 text-lg font-semibold">Start New Chat</h3>
          </div>
          <p class="text-blue-100 mb-4">
            Ask questions about your electrical drawings using AI.
          </p>
          <div class="flex items-center font-medium">
            Open Chat
            <svg class="ml-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>
      </div>

      <!-- Notes Section -->
      <div v-if="project.notes" class="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-3">Notes</h3>
        <p class="text-gray-600 whitespace-pre-wrap">{{ project.notes }}</p>
      </div>
    </div>

    <!-- Edit Modal -->
    <ProjectForm
      v-if="showEditModal && project"
      :project="project"
      @submit="handleEditProject"
      @cancel="showEditModal = false"
    />
  </div>
</template>
