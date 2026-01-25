<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon, PaperAirplaneIcon } from '@heroicons/vue/24/outline'
import { useProjectsStore } from '@/stores/projects'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()

const loading = ref(false)
const error = ref<string | null>(null)
const messageInput = ref('')

const projectId = computed(() => Number(route.params.id))
const conversationId = computed(() => route.params.conversationId ? Number(route.params.conversationId) : null)
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

function sendMessage() {
  if (!messageInput.value.trim()) return
  // TODO: Implement message sending
  console.log('Send message:', messageInput.value)
  messageInput.value = ''
}

onMounted(() => {
  if (!project.value || project.value.id !== projectId.value) {
    loadProject()
  }
})
</script>

<template>
  <div class="project-chat h-screen flex flex-col bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-4 py-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center">
          <button
            type="button"
            class="inline-flex items-center text-gray-600 hover:text-gray-900 mr-4"
            @click="goBack"
          >
            <ArrowLeftIcon class="h-5 w-5" />
          </button>
          <div>
            <h1 class="text-lg font-semibold text-gray-900">
              {{ conversationId ? 'Chat' : 'New Chat' }}
            </h1>
            <p v-if="project" class="text-sm text-gray-500">
              {{ project.name }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex-1 flex justify-center items-center">
      <LoadingSpinner size="large" text="Loading..." />
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="flex-1 p-4">
      <ErrorAlert :message="error" />
    </div>

    <!-- Chat Layout (20% chat / 80% viewer) -->
    <div v-else class="flex-1 flex overflow-hidden">
      <!-- Chat Panel (20%) -->
      <div class="w-1/5 min-w-[280px] bg-white border-r border-gray-200 flex flex-col">
        <!-- Messages Area -->
        <div class="flex-1 overflow-y-auto p-4">
          <div class="text-center py-16">
            <p class="text-gray-500 mb-2">Start a conversation</p>
            <p class="text-sm text-gray-400">
              Ask questions about your electrical drawings.
            </p>
            <p class="text-xs text-gray-400 mt-4">
              (Full implementation in Phase 4)
            </p>
          </div>
        </div>

        <!-- Input Area -->
        <div class="p-4 border-t border-gray-200">
          <div class="flex gap-2">
            <input
              v-model="messageInput"
              type="text"
              placeholder="Ask a question..."
              class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              @keyup.enter="sendMessage"
            />
            <button
              type="button"
              class="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              :disabled="!messageInput.trim()"
              @click="sendMessage"
            >
              <PaperAirplaneIcon class="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>

      <!-- PDF Viewer Panel (80%) -->
      <div class="flex-1 bg-gray-100 flex items-center justify-center">
        <div class="text-center">
          <p class="text-gray-500 mb-2">PDF Viewer</p>
          <p class="text-sm text-gray-400">
            Source documents will be displayed here.
          </p>
          <p class="text-xs text-gray-400 mt-4">
            (Full implementation in Phase 4)
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
