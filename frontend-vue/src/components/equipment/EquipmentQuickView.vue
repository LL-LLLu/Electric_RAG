<script setup lang="ts">
import { watch } from 'vue'
import {
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'
import { XMarkIcon, ArrowLeftIcon, ExclamationTriangleIcon } from '@heroicons/vue/24/outline'
import { useEquipmentQuickView } from '@/composables/useEquipmentQuickView'
import EquipmentDetail from './EquipmentDetail.vue'

const quickView = useEquipmentQuickView()

function handleNavigateToEquipment(tag: string) {
  quickView.open(tag)
}

// Prevent body scroll when drawer is open
watch(() => quickView.isOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : ''
})
</script>

<template>
  <TransitionRoot :show="quickView.isOpen" as="template">
    <div class="fixed inset-0 z-50 overflow-hidden">
      <!-- Backdrop -->
      <TransitionChild
        as="template"
        enter="ease-out duration-300"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-200"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div
          class="absolute inset-0 bg-black/30 transition-opacity"
          @click="quickView.close()"
        />
      </TransitionChild>

      <!-- Panel -->
      <TransitionChild
        as="template"
        enter="transform transition ease-in-out duration-300"
        enter-from="translate-x-full"
        enter-to="translate-x-0"
        leave="transform transition ease-in-out duration-200"
        leave-from="translate-x-0"
        leave-to="translate-x-full"
      >
        <div class="absolute inset-y-0 right-0 w-full max-w-[450px] flex flex-col bg-white dark:bg-gray-800 shadow-xl">
          <!-- Header -->
          <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 flex-shrink-0">
            <div class="flex items-center gap-2">
              <button
                v-if="quickView.history.length > 0"
                type="button"
                class="p-1.5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors"
                title="Go back"
                @click="quickView.goBack()"
              >
                <ArrowLeftIcon class="h-4 w-4" />
              </button>
              <h2 class="text-sm font-semibold text-gray-700 dark:text-gray-200">
                Equipment Details
              </h2>
              <span
                v-if="quickView.currentTag"
                class="text-xs text-gray-500 dark:text-gray-400"
              >
                — {{ quickView.currentTag }}
              </span>
            </div>
            <button
              type="button"
              class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors"
              @click="quickView.close()"
              aria-label="Close panel"
            >
              <XMarkIcon class="h-5 w-5" />
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-y-auto">
            <!-- Loading state -->
            <div v-if="quickView.loading" class="flex items-center justify-center h-64">
              <div class="text-center">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3"></div>
                <p class="text-sm text-gray-500 dark:text-gray-400">Loading equipment data...</p>
              </div>
            </div>

            <!-- Error state -->
            <div v-else-if="quickView.error" class="p-6">
              <div class="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <ExclamationTriangleIcon class="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p class="text-sm font-medium text-red-800 dark:text-red-300">{{ quickView.error }}</p>
                  <button
                    v-if="quickView.currentTag"
                    type="button"
                    class="mt-2 text-sm text-red-600 dark:text-red-400 hover:underline"
                    @click="quickView.open(quickView.currentTag!)"
                  >
                    Try again
                  </button>
                </div>
              </div>
            </div>

            <!-- Equipment detail -->
            <div v-else-if="quickView.equipment" class="quickview-content">
              <EquipmentDetail
                :equipment="quickView.equipment"
                @close="quickView.close()"
                @navigate-to-equipment="handleNavigateToEquipment"
              />
            </div>
          </div>
        </div>
      </TransitionChild>
    </div>
  </TransitionRoot>
</template>

<style scoped>
.quickview-content :deep(.equipment-detail) {
  border: none;
  border-radius: 0;
  box-shadow: none;
}

.quickview-content :deep(.equipment-detail > div:first-child) {
  /* Hide the header section since we have our own header */
  display: none;
}

.quickview-content :deep(.equipment-detail > div:last-child) {
  max-height: none;
}
</style>
