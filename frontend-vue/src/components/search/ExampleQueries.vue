<script setup lang="ts">
import { LightBulbIcon } from '@heroicons/vue/24/outline'

const emit = defineEmits<{
  select: [query: string]
}>()

const exampleQueries = [
  { text: 'Find VFD-101', description: 'Search for specific equipment' },
  { text: 'What controls pump P-201?', description: 'Find control relationships' },
  { text: 'Show breakers in MCC-3', description: 'List equipment by location' },
  { text: 'Motor specifications for M-101', description: 'Get equipment details' },
  { text: 'Electrical drawings for Area 2', description: 'Find documents by area' }
]

function selectQuery(query: string) {
  emit('select', query)
}
</script>

<template>
  <div class="example-queries">
    <div class="flex items-center gap-2 mb-3">
      <LightBulbIcon class="h-5 w-5 text-amber-500" />
      <span class="text-sm font-medium text-gray-700">Try an example:</span>
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="example in exampleQueries"
        :key="example.text"
        type="button"
        class="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
        :title="example.description"
        @click="selectQuery(example.text)"
      >
        {{ example.text }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.example-queries {
  width: 100%;
}
</style>
