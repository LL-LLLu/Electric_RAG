<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { MagnifyingGlassIcon, SparklesIcon, DocumentMagnifyingGlassIcon, ClockIcon, XMarkIcon, CpuChipIcon } from '@heroicons/vue/24/outline'
import { useSearchStore } from '@/stores/search'
import * as equipmentApi from '@/api/equipment'
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

const searchStore = useSearchStore()
const showDropdown = ref(false)
const equipmentSuggestions = ref<equipmentApi.AutocompleteSuggestion[]>([])
const isLoadingSuggestions = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

const inputValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value)
})

const hasHistory = computed(() => searchStore.recentQueries.length > 0)
const hasSuggestions = computed(() => equipmentSuggestions.value.length > 0)
const showHistorySection = computed(() => hasHistory.value && !inputValue.value.trim())
const showSuggestionsSection = computed(() => hasSuggestions.value && inputValue.value.trim().length >= 2)
const isMac = computed(() => navigator.platform.toUpperCase().indexOf('MAC') >= 0)

// Watch for input changes and fetch equipment suggestions
watch(() => props.modelValue, (newValue) => {
  if (debounceTimer) clearTimeout(debounceTimer)

  if (!newValue || newValue.trim().length < 2) {
    equipmentSuggestions.value = []
    return
  }

  debounceTimer = setTimeout(async () => {
    try {
      isLoadingSuggestions.value = true
      const response = await equipmentApi.autocomplete(newValue.trim(), 8)
      equipmentSuggestions.value = response.suggestions
    } catch (err) {
      console.error('Failed to fetch suggestions:', err)
      equipmentSuggestions.value = []
    } finally {
      isLoadingSuggestions.value = false
    }
  }, 200)
})

function toggleMode() {
  const newMode = props.mode === 'ai' ? 'search' : 'ai'
  emit('update:mode', newMode)
}

function handleSubmit() {
  if (inputValue.value.trim()) {
    showDropdown.value = false
    emit('submit')
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
  } else if (event.key === 'Escape') {
    showDropdown.value = false
  }
}

function handleFocus() {
  showDropdown.value = true
}

function handleBlur() {
  // Delay to allow click on dropdown items
  setTimeout(() => {
    showDropdown.value = false
  }, 200)
}

function selectHistoryItem(query: string) {
  inputValue.value = query
  showDropdown.value = false
  emit('submit')
}

function selectSuggestion(tag: string) {
  inputValue.value = tag
  showDropdown.value = false
  equipmentSuggestions.value = []
  emit('submit')
}

function removeHistoryItem(event: Event, query: string) {
  event.stopPropagation()
  searchStore.removeFromHistory(query)
}

function clearAllHistory(event: Event) {
  event.stopPropagation()
  searchStore.clearHistory()
}
</script>

<template>
  <div class="search-box">
    <div class="flex flex-col sm:flex-row gap-3">
      <!-- Search Input with History Dropdown -->
      <div class="relative flex-1">
        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <MagnifyingGlassIcon class="h-5 w-5 text-gray-400" />
        </div>
        <input
          v-model="inputValue"
          type="text"
          class="block w-full pl-10 pr-16 py-3 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900"
          :placeholder="mode === 'ai' ? 'Ask a question about your documents...' : 'Search for equipment, documents...'"
          @keydown="handleKeydown"
          @focus="handleFocus"
          @blur="handleBlur"
        />
        <!-- Keyboard shortcut hint -->
        <div class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
          <kbd class="hidden sm:inline-flex items-center px-2 py-1 text-xs text-gray-400 bg-gray-100 border border-gray-200 rounded">
            <span class="mr-0.5">{{ isMac ? '⌘' : 'Ctrl' }}</span>K
          </kbd>
        </div>

        <!-- Dropdown with History and Suggestions -->
        <div
          v-if="showDropdown && (showHistorySection || showSuggestionsSection)"
          class="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-80 overflow-y-auto"
        >
          <!-- Equipment Suggestions Section -->
          <div v-if="showSuggestionsSection">
            <div class="flex items-center px-3 py-2 border-b border-gray-100 bg-blue-50">
              <CpuChipIcon class="h-3.5 w-3.5 mr-1 text-blue-500" />
              <span class="text-xs font-medium text-blue-600">Equipment Tags</span>
            </div>
            <ul class="py-1">
              <li
                v-for="suggestion in equipmentSuggestions"
                :key="suggestion.tag"
                class="flex items-center justify-between px-3 py-2 hover:bg-blue-50 cursor-pointer"
                @click="selectSuggestion(suggestion.tag)"
              >
                <span class="text-sm text-gray-900 font-medium">{{ suggestion.tag }}</span>
                <span v-if="suggestion.type" class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
                  {{ suggestion.type }}
                </span>
              </li>
            </ul>
          </div>

          <!-- Recent Searches Section -->
          <div v-if="showHistorySection">
            <div class="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50">
              <span class="text-xs font-medium text-gray-500 flex items-center">
                <ClockIcon class="h-3.5 w-3.5 mr-1" />
                Recent Searches
              </span>
              <button
                class="text-xs text-gray-400 hover:text-red-500 transition-colors"
                @click="clearAllHistory"
              >
                Clear all
              </button>
            </div>
            <ul class="py-1">
              <li
                v-for="historyQuery in searchStore.recentQueries"
                :key="historyQuery"
                class="flex items-center justify-between px-3 py-2 hover:bg-gray-50 cursor-pointer group"
                @click="selectHistoryItem(historyQuery)"
              >
                <span class="text-sm text-gray-700 truncate flex-1">{{ historyQuery }}</span>
                <button
                  class="ml-2 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  @click="removeHistoryItem($event, historyQuery)"
                  title="Remove from history"
                >
                  <XMarkIcon class="h-4 w-4" />
                </button>
              </li>
            </ul>
          </div>
        </div>
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
