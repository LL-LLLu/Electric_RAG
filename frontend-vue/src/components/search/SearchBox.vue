<script setup lang="ts">
import { computed } from 'vue'
import { MagnifyingGlassIcon, SparklesIcon, DocumentMagnifyingGlassIcon } from '@heroicons/vue/24/outline'
import type { SearchMode } from '@/types'

const props = defineProps<{
  modelValue: string
  mode: SearchMode
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:mode': [mode: SearchMode]
  submit: []
}>()

const inputValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value)
})

function toggleMode() {
  const newMode = props.mode === 'ai' ? 'search' : 'ai'
  emit('update:mode', newMode)
}

function handleSubmit() {
  if (inputValue.value.trim()) {
    emit('submit')
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
  }
}
</script>

<template>
  <div class="search-box">
    <div class="flex flex-col sm:flex-row gap-3">
      <!-- Search Input -->
      <div class="relative flex-1">
        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <MagnifyingGlassIcon class="h-5 w-5 text-gray-400" />
        </div>
        <input
          v-model="inputValue"
          type="text"
          class="block w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900"
          :placeholder="mode === 'ai' ? 'Ask a question about your documents...' : 'Search for equipment, documents...'"
          @keydown="handleKeydown"
        />
      </div>

      <!-- Mode Toggle -->
      <div class="flex gap-2">
        <button
          type="button"
          class="inline-flex items-center px-4 py-2 border rounded-lg text-sm font-medium transition-colors"
          :class="mode === 'ai'
            ? 'bg-purple-100 border-purple-300 text-purple-700 hover:bg-purple-200'
            : 'bg-gray-100 border-gray-300 text-gray-700 hover:bg-gray-200'"
          @click="toggleMode"
        >
          <SparklesIcon v-if="mode === 'ai'" class="h-4 w-4 mr-2" />
          <DocumentMagnifyingGlassIcon v-else class="h-4 w-4 mr-2" />
          {{ mode === 'ai' ? 'AI Answer' : 'Search Only' }}
        </button>

        <!-- Submit Button -->
        <button
          type="button"
          class="inline-flex items-center px-6 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="!modelValue.trim()"
          @click="handleSubmit"
        >
          <MagnifyingGlassIcon class="h-4 w-4 mr-2" />
          Search
        </button>
      </div>
    </div>

    <!-- Mode Description -->
    <p class="mt-2 text-sm text-gray-500">
      <template v-if="mode === 'ai'">
        <SparklesIcon class="inline h-4 w-4 mr-1 text-purple-500" />
        AI will analyze your documents and provide a detailed answer with sources.
      </template>
      <template v-else>
        <DocumentMagnifyingGlassIcon class="inline h-4 w-4 mr-1 text-gray-400" />
        Search returns matching documents and equipment without AI interpretation.
      </template>
    </p>
  </div>
</template>

<style scoped>
.search-box {
  width: 100%;
}
</style>
