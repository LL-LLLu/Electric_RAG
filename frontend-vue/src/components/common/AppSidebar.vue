<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useAppStore } from '@/stores/app'
import {
  MagnifyingGlassIcon,
  ArrowUpTrayIcon,
  CpuChipIcon,
  DocumentTextIcon,
  EyeIcon
} from '@heroicons/vue/24/outline'

const appStore = useAppStore()

const navigation = [
  { name: 'Search', to: '/', icon: MagnifyingGlassIcon },
  { name: 'Upload', to: '/upload', icon: ArrowUpTrayIcon },
  { name: 'Equipment', to: '/equipment', icon: CpuChipIcon },
  { name: 'Documents', to: '/documents', icon: DocumentTextIcon },
  { name: 'Viewer', to: '/viewer', icon: EyeIcon }
]
</script>

<template>
  <div class="flex h-full w-64 flex-col bg-gray-800">
    <!-- Logo/Title -->
    <div class="flex h-16 shrink-0 items-center px-6">
      <h1 class="text-xl font-bold text-white">Electric RAG</h1>
    </div>

    <!-- Navigation -->
    <nav class="flex flex-1 flex-col px-4">
      <ul role="list" class="flex flex-1 flex-col gap-y-1">
        <li v-for="item in navigation" :key="item.name">
          <RouterLink
            :to="item.to"
            class="group flex gap-x-3 rounded-md p-3 text-sm font-medium leading-6 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
            active-class="bg-gray-900 text-white"
          >
            <component
              :is="item.icon"
              class="h-6 w-6 shrink-0"
              aria-hidden="true"
            />
            {{ item.name }}
          </RouterLink>
        </li>
      </ul>
    </nav>

    <!-- Stats at bottom -->
    <div class="border-t border-gray-700 p-4">
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
