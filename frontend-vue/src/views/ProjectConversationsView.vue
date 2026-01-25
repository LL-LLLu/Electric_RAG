<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon, ChatBubbleLeftRightIcon, PlusIcon } from '@heroicons/vue/24/outline'
import { useProjectsStore } from '@/stores/projects'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()

const loading = ref(false)
const error = ref<string | null>(null)

const projectId = computed(() => Number(route.params.id))
const project = computed(() => projectsStore.currentProject)

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

function goBack() {
  router.push({ name: 'project-dashboard', params: { id: projectId.value } })
}

function startNewChat() {
  router.push({ name: 'project-chat', params: { id: projectId.value } })
}

onMounted(() => {
  if (!project.value || project.value.id !== projectId.value) {
    loadProject()
  }
})
</script>

<template>
  <div class="project-conversations min-h-screen bg-gray-50">
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
            <h1 class="text-3xl font-bold text-gray-900 mb-2">Conversations</h1>
            <p v-if="project" class="text-gray-600">
              Chat history for {{ project.name }}
            </p>
          </div>
          <button
            type="button"
            class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            @click="startNewChat"
          >
            <PlusIcon class="h-5 w-5 mr-2" />
            New Chat
          </button>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-16">
        <LoadingSpinner size="large" text="Loading..." />
      </div>

      <!-- Error State -->
      <ErrorAlert v-else-if="error" :message="error" class="mb-6" />

      <!-- Placeholder Content -->
      <div v-else class="text-center py-16 bg-white rounded-lg border border-gray-200">
        <ChatBubbleLeftRightIcon class="h-16 w-16 mx-auto text-gray-300 mb-4" />
        <h3 class="text-lg font-medium text-gray-900 mb-2">Conversation History</h3>
        <p class="text-gray-500 mb-4">
          View and resume previous chat sessions.
        </p>
        <p class="text-sm text-gray-400">
          (Full implementation in Phase 4)
        </p>
      </div>
    </div>
  </div>
</template>
