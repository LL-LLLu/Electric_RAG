<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import type { Message } from '@/types'
import ChatMessage from './ChatMessage.vue'

const props = defineProps<{
  messages: Message[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'viewSource', documentId: number, pageNumber: number): void
}>()

const messagesContainer = ref<HTMLElement | null>(null)

// Auto-scroll to bottom when new messages arrive
watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }
)

function handleViewSource(documentId: number, pageNumber: number) {
  emit('viewSource', documentId, pageNumber)
}
</script>

<template>
  <div
    ref="messagesContainer"
    class="chat-message-list flex-1 overflow-y-auto p-4 space-y-4"
  >
    <!-- Empty state -->
    <div v-if="messages.length === 0 && !loading" class="text-center py-16">
      <p class="text-gray-500 mb-2">Start a conversation</p>
      <p class="text-sm text-gray-400">
        Ask questions about your electrical drawings.
      </p>
    </div>

    <!-- Messages -->
    <ChatMessage
      v-for="message in messages"
      :key="message.id"
      :message="message"
      @view-source="handleViewSource"
    />

    <!-- Loading indicator -->
    <div v-if="loading" class="flex gap-3">
      <div class="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
        <div class="animate-pulse w-3 h-3 rounded-full bg-gray-400" />
      </div>
      <div class="flex-1">
        <div class="inline-block px-4 py-2 bg-gray-100 rounded-lg">
          <div class="flex items-center gap-1">
            <div class="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style="animation-delay: 0ms" />
            <div class="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style="animation-delay: 150ms" />
            <div class="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style="animation-delay: 300ms" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
