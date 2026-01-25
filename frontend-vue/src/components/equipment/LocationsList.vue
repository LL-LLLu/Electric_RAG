<script setup lang="ts">
import { useRouter } from 'vue-router'
import { DocumentTextIcon, ChevronRightIcon } from '@heroicons/vue/24/outline'
import type { EquipmentLocation } from '@/types'

defineProps<{
  locations: EquipmentLocation[]
}>()

const router = useRouter()

function navigateToDocument(location: EquipmentLocation) {
  // We need to find document ID from filename - for now navigate to viewer
  // The viewer will need to handle document lookup by filename
  router.push({
    name: 'viewer',
    query: {
      filename: location.document_filename,
      page: location.page_number
    }
  })
}
</script>

<template>
  <div class="locations-list">
    <h4 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
      <DocumentTextIcon class="h-4 w-4" />
      Document Locations ({{ locations.length }})
    </h4>

    <div v-if="locations.length === 0" class="text-sm text-gray-500 italic">
      No document locations found.
    </div>

    <div v-else class="space-y-2">
      <button
        v-for="(location, index) in locations"
        :key="index"
        type="button"
        class="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors group"
        @click="navigateToDocument(location)"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-900 truncate">
                {{ location.document_title || location.document_filename }}
              </span>
              <span class="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded">
                Page {{ location.page_number }}
              </span>
            </div>
            <p
              v-if="location.context_text"
              class="mt-1 text-xs text-gray-600 line-clamp-2"
            >
              {{ location.context_text }}
            </p>
          </div>
          <ChevronRightIcon
            class="h-4 w-4 text-gray-400 group-hover:text-gray-600 flex-shrink-0 ml-2"
          />
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
