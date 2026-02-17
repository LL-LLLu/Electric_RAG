<script setup lang="ts">
import { ref, watch } from 'vue'
import api from '@/api/index'
import EquipmentTagLink from './EquipmentTagLink.vue'

const props = defineProps<{
  documentId: number
  pageNumber: number
  excludeTag: string
}>()

interface PageEquipment { tag: string; equipment_type: string }
const others = ref<PageEquipment[]>([])

watch(
  [() => props.documentId, () => props.pageNumber],
  async ([docId, page]) => {
    try {
      const { data } = await api.get(`/api/documents/${docId}/page/${page}/equipment`)
      others.value = (data.equipment || [])
        .filter((e: PageEquipment) => e.tag.toUpperCase() !== props.excludeTag.toUpperCase())
        .slice(0, 5)
    } catch {
      others.value = []
    }
  },
  { immediate: true }
)
</script>

<template>
  <div v-if="others.length > 0" class="flex flex-wrap items-center gap-1 mt-1">
    <span class="text-xs text-gray-500 dark:text-gray-400">Also here:</span>
    <EquipmentTagLink v-for="eq in others" :key="eq.tag" :tag="eq.tag" />
  </div>
</template>
