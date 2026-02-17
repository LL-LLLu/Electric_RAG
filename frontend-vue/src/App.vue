<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterView, useRouter, useRoute } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import { useThemeStore } from '@/stores/theme'
import { useEquipmentQuickView } from '@/composables/useEquipmentQuickView'

const themeStore = useThemeStore()
const router = useRouter()
const route = useRoute()

function handleGlobalKeydown(event: KeyboardEvent) {
  // Cmd+K (Mac) or Ctrl+K (Windows) to focus search
  if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
    event.preventDefault()

    // If not on search page, navigate there
    if (route.path !== '/') {
      router.push('/')
    }

    // Focus the search input after a short delay to allow navigation
    setTimeout(() => {
      const searchInput = document.querySelector('input[type="text"][placeholder*="Search"], input[type="text"][placeholder*="Ask"]') as HTMLInputElement
      if (searchInput) {
        searchInput.focus()
        searchInput.select()
      }
    }, 100)
  }
}

// Global click handler for equipment tag links rendered via v-html
function handleEquipmentTagClick(event: Event) {
  const target = event.target as HTMLElement
  if (target.classList.contains('equipment-tag-link')) {
    const tag = target.dataset.tag
    if (tag) {
      const quickView = useEquipmentQuickView()
      quickView.open(tag)
    }
  }
}

onMounted(() => {
  themeStore.init()
  window.addEventListener('keydown', handleGlobalKeydown)
  document.addEventListener('click', handleEquipmentTagClick)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  document.removeEventListener('click', handleEquipmentTagClick)
})
</script>

<template>
  <DefaultLayout>
    <RouterView />
  </DefaultLayout>
</template>

<style scoped>
/* Global app styles can go here */
</style>
