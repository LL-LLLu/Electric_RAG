import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  // Landing page - new home with projects
  {
    path: '/',
    name: 'home',
    alias: '/landing',
    component: () => import('@/views/LandingView.vue')
  },
  {
    path: '/landing',
    name: 'landing',
    redirect: '/'
  },

  // Unassigned documents
  {
    path: '/unassigned-documents',
    name: 'unassigned-documents',
    component: () => import('@/views/UnassignedDocumentsView.vue')
  },

  // Project routes
  {
    path: '/projects/:id',
    name: 'project-dashboard',
    component: () => import('@/views/ProjectDashboardView.vue')
  },
  {
    path: '/projects/:id/documents',
    name: 'project-documents',
    component: () => import('@/views/ProjectDocumentsView.vue')
  },
  {
    path: '/projects/:id/conversations',
    name: 'project-conversations',
    component: () => import('@/views/ProjectConversationsView.vue')
  },
  {
    path: '/projects/:id/chat/:conversationId?',
    name: 'project-chat',
    component: () => import('@/views/ProjectChatView.vue')
  },

  // Legacy routes (maintained for backward compatibility)
  {
    path: '/search',
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
