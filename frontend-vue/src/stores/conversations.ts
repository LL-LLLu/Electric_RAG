import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  Conversation,
  ConversationDetail,
  ConversationCreate,
  Message,
} from '@/types'
import conversationsApi from '@/api/conversations'

export const useConversationsStore = defineStore('conversations', () => {
  // State
  const conversations = ref<Conversation[]>([])
  const currentConversation = ref<ConversationDetail | null>(null)
  const loading = ref(false)
  const sending = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const messages = computed(() => currentConversation.value?.messages ?? [])
  const hasConversation = computed(() => currentConversation.value !== null)

  // Actions
  async function fetchProjectConversations(projectId: number) {
    loading.value = true
    error.value = null
    try {
      conversations.value = await conversationsApi.listByProject(projectId)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch conversations'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createConversation(projectId: number, data: ConversationCreate = {}) {
    loading.value = true
    error.value = null
    try {
      const conversation = await conversationsApi.create(projectId, data)
      conversations.value.unshift(conversation)
      // Initialize as detail with empty messages
      currentConversation.value = {
        ...conversation,
        messages: [],
      }
      return conversation
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create conversation'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchConversation(conversationId: number) {
    loading.value = true
    error.value = null
    try {
      currentConversation.value = await conversationsApi.get(conversationId)
      return currentConversation.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch conversation'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateConversation(conversationId: number, data: { title?: string }) {
    error.value = null
    try {
      const updated = await conversationsApi.update(conversationId, data)
      // Update in list
      const index = conversations.value.findIndex((c) => c.id === conversationId)
      if (index !== -1) {
        conversations.value[index] = updated
      }
      // Update current if it's the same
      if (currentConversation.value?.id === conversationId) {
        currentConversation.value.title = updated.title
      }
      return updated
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update conversation'
      throw e
    }
  }

  async function deleteConversation(conversationId: number) {
    error.value = null
    try {
      await conversationsApi.delete(conversationId)
      // Remove from list
      conversations.value = conversations.value.filter((c) => c.id !== conversationId)
      // Clear current if it's the same
      if (currentConversation.value?.id === conversationId) {
        currentConversation.value = null
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to delete conversation'
      throw e
    }
  }

  async function sendMessage(content: string): Promise<Message | null> {
    if (!currentConversation.value) {
      error.value = 'No active conversation'
      return null
    }

    sending.value = true
    error.value = null

    // Add user message optimistically
    const userMessage: Message = {
      id: Date.now(), // Temporary ID
      conversation_id: currentConversation.value.id,
      role: 'user',
      content,
      sources: null,
      created_at: new Date().toISOString(),
    }
    currentConversation.value.messages.push(userMessage)

    try {
      // Send and get AI response
      const assistantMessage = await conversationsApi.sendMessage(
        currentConversation.value.id,
        { content }
      )
      // Add assistant response
      currentConversation.value.messages.push(assistantMessage)

      // Update conversation in list (for updated_at and potentially title)
      if (currentConversation.value) {
        const convId = currentConversation.value.id
        const conv = conversations.value.find((c) => c.id === convId)
        if (conv) {
          conv.updated_at = new Date().toISOString()
        }
      }

      return assistantMessage
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to send message'
      // Remove optimistic message on error
      currentConversation.value.messages.pop()
      throw e
    } finally {
      sending.value = false
    }
  }

  function clearCurrentConversation() {
    currentConversation.value = null
  }

  function $reset() {
    conversations.value = []
    currentConversation.value = null
    loading.value = false
    sending.value = false
    error.value = null
  }

  return {
    // State
    conversations,
    currentConversation,
    loading,
    sending,
    error,
    // Getters
    messages,
    hasConversation,
    // Actions
    fetchProjectConversations,
    createConversation,
    fetchConversation,
    updateConversation,
    deleteConversation,
    sendMessage,
    clearCurrentConversation,
    $reset,
  }
})
