<script setup lang="ts">
import { useEquipmentStore } from '@/stores/equipment'

const equipmentStore = useEquipmentStore()
</script>

<template>
  <div class="equipment-view">
    <div class="container mx-auto px-4 py-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-6">Equipment</h1>
      <p class="text-gray-600">
        Browse and filter extracted equipment from documents.
        {{ equipmentStore.totalCount }} equipment items.
      </p>
      <!-- Equipment list will be implemented in Task 7 -->
    </div>
  </div>
</template>

<style scoped>
.equipment-view {
  min-height: 100vh;
}
</style>
