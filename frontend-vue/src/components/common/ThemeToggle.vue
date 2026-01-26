<script setup lang="ts">
import { useThemeStore, type ThemeMode } from '@/stores/theme'
import { SunIcon, MoonIcon, ComputerDesktopIcon } from '@heroicons/vue/24/outline'

const themeStore = useThemeStore()

const options: { value: ThemeMode; label: string; icon: typeof SunIcon }[] = [
  { value: 'light', label: 'Light', icon: SunIcon },
  { value: 'dark', label: 'Dark', icon: MoonIcon },
  { value: 'system', label: 'System', icon: ComputerDesktopIcon },
]

function selectTheme(mode: ThemeMode) {
  themeStore.setTheme(mode)
}
</script>

<template>
  <div class="theme-toggle">
    <div class="flex rounded-lg bg-gray-700 p-1">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="flex items-center justify-center p-1.5 rounded-md transition-colors"
        :class="[
          themeStore.theme === option.value
            ? 'bg-gray-600 text-white'
            : 'text-gray-400 hover:text-gray-200'
        ]"
        :title="option.label"
        @click="selectTheme(option.value)"
      >
        <component :is="option.icon" class="h-4 w-4" />
      </button>
    </div>
  </div>
</template>
