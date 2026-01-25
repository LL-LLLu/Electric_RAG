import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'search',
    component: () => import('@/views/SearchView.vue')
  },
  {
    path: '/upload',
    name: 'upload',
    component: () => import('@/views/UploadView.vue')
  },
  {
    path: '/equipment',
    name: 'equipment',
    component: () => import('@/views/EquipmentView.vue')
  },
  {
    path: '/documents',
    name: 'documents',
    component: () => import('@/views/DocumentsView.vue')
  },
  {
    path: '/viewer/:docId?/:pageNum?',
    name: 'viewer',
    component: () => import('@/views/ViewerView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
