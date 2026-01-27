<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useAppStore } from '@/stores/app'
import ThemeToggle from '@/components/common/ThemeToggle.vue'
import {
  MagnifyingGlassIcon,
  ArrowUpTrayIcon,
  CpuChipIcon,
  DocumentTextIcon,
  EyeIcon,
  ChevronLeftIcon,
  ChevronRightIcon
} from '@heroicons/vue/24/outline'

const appStore = useAppStore()

const isCollapsed = computed(() => appStore.sidebarCollapsed)

const navigation = [
  { name: 'Search', to: '/', icon: MagnifyingGlassIcon },
  { name: 'Upload', to: '/upload', icon: ArrowUpTrayIcon },
  { name: 'Equipment', to: '/equipment', icon: CpuChipIcon },
  { name: 'Documents', to: '/documents', icon: DocumentTextIcon },
  { name: 'Viewer', to: '/viewer', icon: EyeIcon }
]

function toggleSidebar() {
  appStore.toggleSidebar()
}
</script>

<template>
  <div
    class="flex h-full flex-col bg-gray-800 transition-all duration-300"
    :class="isCollapsed ? 'w-16' : 'w-64'"
  >
    <!-- Logo/Title with Collapse Toggle -->
    <div class="flex h-16 shrink-0 items-center justify-between" :class="isCollapsed ? 'px-2' : 'px-4'">
      <h1 v-if="!isCollapsed" class="text-xl font-bold text-white">Electric RAG</h1>
      <span v-else class="text-xl font-bold text-white">E</span>

      <!-- Collapse Toggle Button -->
      <button
        @click="toggleSidebar"
        class="flex h-8 w-8 items-center justify-center rounded-md text-gray-400 hover:bg-gray-700 hover:text-white transition-colors"
        :title="isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
      >
        <ChevronLeftIcon v-if="!isCollapsed" class="h-5 w-5" />
        <ChevronRightIcon v-else class="h-5 w-5" />
      </button>
    </div>

    <!-- Navigation -->
    <nav class="flex flex-1 flex-col" :class="isCollapsed ? 'px-2' : 'px-4'">
      <ul role="list" class="flex flex-1 flex-col gap-y-1">
        <li v-for="item in navigation" :key="item.name">
          <RouterLink
            :to="item.to"
            class="group flex rounded-md text-sm font-medium leading-6 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
            :class="isCollapsed ? 'justify-center p-3' : 'gap-x-3 p-3'"
            active-class="bg-gray-900 text-white"
            :title="isCollapsed ? item.name : undefined"
          >
            <component
              :is="item.icon"
              class="h-6 w-6 shrink-0"
              aria-hidden="true"
            />
            <span v-if="!isCollapsed">{{ item.name }}</span>
          </RouterLink>
        </li>
      </ul>
    </nav>

    <!-- Theme Toggle -->
    <div class="border-t border-gray-700 p-4" :class="isCollapsed ? 'flex justify-center' : ''">
      <div v-if="!isCollapsed" class="flex items-center justify-between">
        <span class="text-xs font-semibold uppercase tracking-wider text-gray-400">Theme</span>
        <ThemeToggle />
      </div>
      <ThemeToggle v-else />
    </div>

    <!-- Stats at bottom (hide when collapsed) -->
    <div v-if="!isCollapsed" class="border-t border-gray-700 p-4">
      <h3 class="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
        Statistics
      </h3>
      <dl class="space-y-2">
        <div class="flex justify-between">
          <dt class="text-sm text-gray-400">Documents</dt>
          <dd class="text-sm font-medium text-white">{{ appStore.stats.documents }}</dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-sm text-gray-400">Equipment</dt>
          <dd class="text-sm font-medium text-white">{{ appStore.stats.equipment }}</dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-sm text-gray-400">Pages</dt>
          <dd class="text-sm font-medium text-white">{{ appStore.stats.pages }}</dd>
        </div>
      </dl>
    </div>
  </div>
</template>
