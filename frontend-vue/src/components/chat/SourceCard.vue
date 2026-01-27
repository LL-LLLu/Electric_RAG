<script setup lang="ts">
import { computed } from 'vue'
import { DocumentTextIcon } from '@heroicons/vue/24/outline'
import type { SourceReference } from '@/types'

const props = defineProps<{
  source: SourceReference
}>()

defineEmits<{
  (e: 'click'): void
}>()

const thumbnailUrl = computed(() => {
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  return `${baseUrl}/api/documents/${props.source.document_id}/page/${props.source.page_number}/thumbnail?width=100`
})

const shortName = computed(() => {
  const name = props.source.document_name
  if (name.length > 20) {
    return name.substring(0, 17) + '...'
  }
  return name
})
</script>

<template>
  <div
    class="source-card flex items-center gap-2 px-2 py-1.5 bg-gray-50 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-100 hover:border-gray-300 transition-colors"
    @click="$emit('click')"
  >
    <!-- Thumbnail -->
    <div class="flex-shrink-0 w-10 h-10 bg-white border border-gray-200 rounded overflow-hidden">
      <img
        :src="thumbnailUrl"
        :alt="`Page ${source.page_number}`"
        class="w-full h-full object-cover"
        @error="($event.target as HTMLImageElement).style.display = 'none'"
      />
      <div class="w-full h-full flex items-center justify-center">
        <DocumentTextIcon class="w-5 h-5 text-gray-300" />
      </div>
    </div>

    <!-- Info -->
    <div class="min-w-0 flex-1">
      <p class="text-xs font-medium text-gray-700 truncate" :title="source.document_name">
        {{ shortName }}
      </p>
      <p class="text-xs text-gray-500">
        Page {{ source.page_number }}
        <span v-if="source.equipment_tag" class="text-blue-600 ml-1">
          {{ source.equipment_tag }}
        </span>
      </p>
    </div>
  </div>
</template>
