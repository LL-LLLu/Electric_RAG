<script setup lang="ts">
import { ref } from 'vue'
import { PaperAirplaneIcon } from '@heroicons/vue/24/outline'

defineProps<{
  disabled?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'send', message: string): void
}>()

const input = ref('')

function handleSubmit() {
  const message = input.value.trim()
  if (!message) return

  emit('send', message)
  input.value = ''
}

function handleKeydown(event: KeyboardEvent) {
  // Submit on Enter, allow Shift+Enter for new line
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
  }
}
</script>

<template>
  <div class="chat-input p-4 border-t border-gray-200 bg-white">
    <div class="flex gap-2">
      <textarea
        v-model="input"
        :placeholder="placeholder || 'Ask a question...'"
        :disabled="disabled"
        rows="1"
        class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none disabled:opacity-50 disabled:cursor-not-allowed"
        @keydown="handleKeydown"
      />
      <button
        type="button"
        :disabled="disabled || !input.trim()"
        class="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        @click="handleSubmit"
      >
        <PaperAirplaneIcon class="h-5 w-5" />
      </button>
    </div>
  </div>
</template>
