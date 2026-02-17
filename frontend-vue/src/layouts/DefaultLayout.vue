<script setup lang="ts">
import AppSidebar from '@/components/common/AppSidebar.vue'
import EquipmentQuickView from '@/components/equipment/EquipmentQuickView.vue'
</script>

<template>
  <div class="flex h-screen bg-gray-50 dark:bg-gray-900">
    <!-- Sidebar -->
    <AppSidebar />

    <!-- Main content area -->
    <main class="flex-1 overflow-auto">
      <div class="h-full">
        <slot />
      </div>
    </main>

    <!-- Global equipment quick-view drawer -->
    <EquipmentQuickView />
  </div>
</template>
