<script setup lang="ts">
import { ref, computed } from 'vue'
import { UserIcon, CpuChipIcon, ClipboardDocumentIcon, CheckIcon } from '@heroicons/vue/24/outline'
import type { Message } from '@/types'
import SourceCard from './SourceCard.vue'

const props = defineProps<{
  message: Message
}>()

const emit = defineEmits<{
  (e: 'viewSource', documentId: number, pageNumber: number): void
}>()

const isUser = computed(() => props.message.role === 'user')
const hasSources = computed(() => props.message.sources && props.message.sources.length > 0)
const copied = ref(false)

// Equipment tag regex - matches common electrical/mechanical equipment tag patterns
const EQUIPMENT_TAG_REGEX = /\b((?:RTU|FAN|AHU|FCU|VAV|MAU|EF|SF|RF|MOT|MTR|VFD|VSD|PMP|BKR|CB|MCCB|RLY|PLC|DCS|TS|PS|FS|LS|PT|FT|LT|TT|CV|MOV|SOV|BV|GV|MCC|SWG|PNL|DP|LP|MDP|XFMR|TX|SW|HS|SS|DS|HMI|OIT|UPS|GEN|DG|EG|CAP)[-_]?[A-Z]?\d{1,4}[A-Z]?)\b/g

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const renderedContent = computed(() => {
  if (isUser.value) return ''
  const escaped = escapeHtml(props.message.content)
  return escaped.replace(EQUIPMENT_TAG_REGEX, (match) => {
    return `<span class="equipment-tag-link" data-tag="${match}" role="button" tabindex="0">${match}</span>`
  })
})

function handleSourceClick(documentId: number, pageNumber: number) {
  emit('viewSource', documentId, pageNumber)
}

async function copyToClipboard() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}
</script>

<template>
  <div
    class="chat-message flex gap-3"
    :class="isUser ? 'flex-row-reverse' : 'flex-row'"
  >
    <!-- Avatar -->
    <div
      class="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
      :class="isUser ? 'bg-blue-100' : 'bg-gray-100'"
    >
      <UserIcon v-if="isUser" class="w-5 h-5 text-blue-600" />
      <CpuChipIcon v-else class="w-5 h-5 text-gray-600" />
    </div>

    <!-- Content -->
    <div class="flex-1 min-w-0" :class="isUser ? 'text-right' : 'text-left'">
      <!-- Message bubble -->
      <div
        class="inline-block px-4 py-2 rounded-lg max-w-[90%] relative group"
        :class="
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white border border-gray-200 text-gray-900'
        "
      >
        <p v-if="isUser" class="text-sm whitespace-pre-wrap break-words">
          {{ message.content }}
        </p>
        <p v-else class="text-sm whitespace-pre-wrap break-words text-left chat-markdown" v-html="renderedContent"></p>

        <!-- Copy button (only for assistant messages) -->
        <button
          v-if="!isUser"
          @click="copyToClipboard"
          class="absolute top-1 right-1 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
          :class="copied ? 'text-green-500' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'"
          :title="copied ? 'Copied!' : 'Copy to clipboard'"
        >
          <CheckIcon v-if="copied" class="w-4 h-4" />
          <ClipboardDocumentIcon v-else class="w-4 h-4" />
        </button>
      </div>

      <!-- Sources (only for assistant messages) -->
      <div v-if="!isUser && hasSources" class="mt-3 space-y-2">
        <p class="text-xs text-gray-500 font-medium">Sources:</p>
        <div class="flex flex-wrap gap-2">
          <SourceCard
            v-for="(source, index) in message.sources"
            :key="index"
            :source="source"
            @click="handleSourceClick(source.document_id, source.page_number)"
          />
        </div>
      </div>

      <!-- Timestamp -->
      <p class="text-xs text-gray-400 mt-1">
        {{ new Date(message.created_at).toLocaleTimeString() }}
      </p>
    </div>
  </div>
</template>

<style>
.chat-markdown .equipment-tag-link {
  color: #2563eb;
  background: #dbeafe;
  padding: 0.1rem 0.4rem;
  border-radius: 9999px;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.85em;
}
.chat-markdown .equipment-tag-link:hover {
  background: #bfdbfe;
}
</style>
