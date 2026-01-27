<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeftIcon,
  ChatBubbleLeftRightIcon,
  PlusIcon,
  TrashIcon,
  ChevronRightIcon,
} from '@heroicons/vue/24/outline'
import { useProjectsStore } from '@/stores/projects'
import { useConversationsStore } from '@/stores/conversations'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()
const conversationsStore = useConversationsStore()

// State
const loading = ref(false)
const error = ref<string | null>(null)
const showDeleteConfirm = ref(false)
const conversationToDelete = ref<number | null>(null)

// Computed
const projectId = computed(() => Number(route.params.id))
const project = computed(() => projectsStore.currentProject)
const conversations = computed(() => conversationsStore.conversations)

// Load project and conversations
async function loadData() {
  loading.value = true
  error.value = null

  try {
    if (!project.value || project.value.id !== projectId.value) {
      await projectsStore.fetchProject(projectId.value)
    }
    await conversationsStore.fetchProjectConversations(projectId.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load conversations'
  } finally {
    loading.value = false
  }
}

// Format date for display
function formatDate(dateStr: string) {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Navigation
function goBack() {
  router.push({ name: 'project-dashboard', params: { id: projectId.value } })
}

function startNewChat() {
  router.push({ name: 'project-chat', params: { id: projectId.value } })
}

function resumeConversation(conversationId: number) {
  router.push({
    name: 'project-chat',
    params: { id: projectId.value, conversationId },
  })
}

// Delete conversation
function confirmDelete(conversationId: number) {
  conversationToDelete.value = conversationId
  showDeleteConfirm.value = true
}

async function deleteConversation() {
  if (!conversationToDelete.value) return

  try {
    await conversationsStore.deleteConversation(conversationToDelete.value)
    showDeleteConfirm.value = false
    conversationToDelete.value = null

    // Refresh project stats
    await projectsStore.fetchProject(projectId.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to delete conversation'
  }
}

// Initialize
onMounted(() => {
  loadData()
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

      <!-- Error Alert -->
      <ErrorAlert v-if="error" :message="error" class="mb-6" @dismiss="error = null" />

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-16">
        <LoadingSpinner size="large" text="Loading conversations..." />
      </div>

      <!-- Empty State -->
      <div
        v-else-if="conversations.length === 0"
        class="text-center py-16 bg-white rounded-lg border border-gray-200"
      >
        <ChatBubbleLeftRightIcon class="h-16 w-16 mx-auto text-gray-300 mb-4" />
        <h3 class="text-lg font-medium text-gray-900 mb-2">No conversations yet</h3>
        <p class="text-gray-500 mb-4">
          Start a chat to ask questions about your electrical drawings.
        </p>
        <button
          type="button"
          class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          @click="startNewChat"
        >
          <PlusIcon class="h-5 w-5 mr-2" />
          Start Your First Chat
        </button>
      </div>

      <!-- Conversations List -->
      <div v-else class="space-y-3">
        <div
          v-for="conversation in conversations"
          :key="conversation.id"
          class="bg-white rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer"
          @click="resumeConversation(conversation.id)"
        >
          <div class="p-4 flex items-center justify-between">
            <div class="flex items-center gap-4 min-w-0 flex-1">
              <div class="p-2 bg-blue-50 rounded-lg flex-shrink-0">
                <ChatBubbleLeftRightIcon class="h-5 w-5 text-blue-600" />
              </div>
              <div class="min-w-0 flex-1">
                <h3 class="text-sm font-medium text-gray-900 truncate">
                  {{ conversation.title || 'New Chat' }}
                </h3>
                <p class="text-xs text-gray-500 mt-0.5">
                  {{ formatDate(conversation.updated_at) }}
                </p>
              </div>
            </div>

            <div class="flex items-center gap-2 ml-4">
              <button
                type="button"
                class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                title="Delete conversation"
                @click.stop="confirmDelete(conversation.id)"
              >
                <TrashIcon class="h-4 w-4" />
              </button>
              <ChevronRightIcon class="h-5 w-5 text-gray-400" />
            </div>
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
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Delete Conversation?</h3>
        <p class="text-gray-600 mb-4">
          Are you sure you want to delete this conversation? This will remove all messages and
          cannot be undone.
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
            @click="deleteConversation"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
