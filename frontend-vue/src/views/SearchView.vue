<script setup lang="ts">
import { useSearchStore } from '@/stores/search'

const searchStore = useSearchStore()
</script>

<template>
  <div class="search-view">
    <div class="container mx-auto px-4 py-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-6">Search Documents</h1>
      <p class="text-gray-600">
        Search across all documents and equipment. Mode: {{ searchStore.mode }}
      </p>
      <!-- Search interface will be implemented in Task 5 -->
    </div>
  </div>
</template>

<style scoped>
.search-view {
  min-height: 100vh;
}
</style>
