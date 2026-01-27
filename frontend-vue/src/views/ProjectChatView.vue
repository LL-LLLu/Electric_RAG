<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon } from '@heroicons/vue/24/outline'
import { useProjectsStore } from '@/stores/projects'
import { useConversationsStore } from '@/stores/conversations'
import * as documentsApi from '@/api/documents'
import type { Document } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import ChatMessageList from '@/components/chat/ChatMessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import PdfViewer from '@/components/viewer/PdfViewer.vue'

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()
const conversationsStore = useConversationsStore()

// State
const loading = ref(false)
const error = ref<string | null>(null)
const documents = ref<Document[]>([])
const viewerDocumentId = ref<number | null>(null)
const viewerPageNumber = ref(1)

// Computed
const projectId = computed(() => Number(route.params.id))
const conversationId = computed(() =>
  route.params.conversationId ? Number(route.params.conversationId) : null
)
const project = computed(() => projectsStore.currentProject)
const messages = computed(() => conversationsStore.messages)
const sending = computed(() => conversationsStore.sending)
const hasConversation = computed(() => conversationsStore.hasConversation)

// Load project and initialize conversation
async function initialize() {
  loading.value = true
  error.value = null

  try {
    // Load project if not already loaded
    if (!project.value || project.value.id !== projectId.value) {
      await projectsStore.fetchProject(projectId.value)
    }

    // Load project documents for the PDF viewer
    documents.value = await documentsApi.listByProject(projectId.value)

    // Load or create conversation
    if (conversationId.value) {
      // Resume existing conversation
      await conversationsStore.fetchConversation(conversationId.value)
    } else {
      // Create new conversation
      await conversationsStore.createConversation(projectId.value, {})
      // Update URL with new conversation ID
      if (conversationsStore.currentConversation) {
        router.replace({
          name: 'project-chat',
          params: {
            id: projectId.value,
            conversationId: conversationsStore.currentConversation.id,
          },
        })
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to initialize chat'
  } finally {
    loading.value = false
  }
}

// Send message
async function handleSendMessage(content: string) {
  if (!hasConversation.value) return

  try {
    const response = await conversationsStore.sendMessage(content)

    // If response has sources, show the first one in the viewer
    if (response?.sources && response.sources.length > 0) {
      const firstSource = response.sources[0]
      if (firstSource) {
        viewerDocumentId.value = firstSource.document_id
        viewerPageNumber.value = firstSource.page_number
      }
    }
  } catch (e) {
    // Error is handled by the store
    console.error('Failed to send message:', e)
  }
}

// View source in PDF viewer
function handleViewSource(documentId: number, pageNumber: number) {
  viewerDocumentId.value = documentId
  viewerPageNumber.value = pageNumber
}

// Navigation
function goBack() {
  router.push({ name: 'project-dashboard', params: { id: projectId.value } })
}

// Watch for route changes (switching conversations)
watch(
  () => route.params.conversationId,
  async (newId) => {
    if (newId && Number(newId) !== conversationsStore.currentConversation?.id) {
      loading.value = true
      try {
        await conversationsStore.fetchConversation(Number(newId))
      } catch (e) {
        error.value = e instanceof Error ? e.message : 'Failed to load conversation'
      } finally {
        loading.value = false
      }
    }
  }
)

// Initialize on mount
onMounted(() => {
  initialize()
})
</script>

<template>
  <div class="project-chat h-screen flex flex-col bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-4 py-3 flex-shrink-0">
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
              {{ conversationsStore.currentConversation?.title || 'New Chat' }}
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
      <div class="w-1/5 min-w-[320px] max-w-[400px] bg-white border-r border-gray-200 flex flex-col">
        <!-- Messages Area -->
        <ChatMessageList
          :messages="messages"
          :loading="sending"
          @view-source="handleViewSource"
        />

        <!-- Input Area -->
        <ChatInput
          :disabled="sending || !hasConversation"
          placeholder="Ask about your electrical drawings..."
          @send="handleSendMessage"
        />
      </div>

      <!-- PDF Viewer Panel (80%) -->
      <div class="flex-1 bg-gray-100">
        <PdfViewer
          :document-id="viewerDocumentId"
          :page-number="viewerPageNumber"
          :documents="documents"
          @document-change="(id: number) => (viewerDocumentId = id)"
          @page-change="(num: number) => (viewerPageNumber = num)"
        />
      </div>
    </div>
  </div>
</template>
