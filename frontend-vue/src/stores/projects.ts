import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Project, ProjectDetail, ProjectCreate, ProjectUpdate } from '@/types'
import { projectsApi } from '@/api/projects'

export const useProjectsStore = defineStore('projects', () => {
  // State
  const projects = ref<Project[]>([])
  const currentProject = ref<ProjectDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Computed
  const hasProjects = computed(() => projects.value.length > 0)
  const activeProjects = computed(() =>
    projects.value.filter(p => p.status === 'active')
  )
  const archivedProjects = computed(() =>
    projects.value.filter(p => p.status === 'archived')
  )

  // Actions
  async function fetchProjects(status?: string) {
    loading.value = true
    error.value = null
    try {
      projects.value = await projectsApi.list(0, 100, status)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch projects'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchProject(id: number) {
    loading.value = true
    error.value = null
    try {
      currentProject.value = await projectsApi.get(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch project'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createProject(data: ProjectCreate): Promise<Project> {
    loading.value = true
    error.value = null
    try {
      const project = await projectsApi.create(data)
      projects.value.unshift(project)
      return project
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create project'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateProject(id: number, data: ProjectUpdate): Promise<Project> {
    loading.value = true
    error.value = null
    try {
      const project = await projectsApi.update(id, data)
      const index = projects.value.findIndex(p => p.id === id)
      if (index !== -1) {
        projects.value[index] = project
      }
      if (currentProject.value?.id === id) {
        currentProject.value = { ...currentProject.value, ...project }
      }
      return project
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update project'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteProject(id: number): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await projectsApi.delete(id)
      const index = projects.value.findIndex(p => p.id === id)
      if (index !== -1) {
        projects.value.splice(index, 1)
      }
      if (currentProject.value?.id === id) {
        currentProject.value = null
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to delete project'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function uploadCoverImage(id: number, file: File): Promise<void> {
    try {
      await projectsApi.uploadCoverImage(id, file)
      // Refresh project to get updated cover image path
      await fetchProject(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to upload cover image'
      throw e
    }
  }

  function clearCurrentProject() {
    currentProject.value = null
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    projects,
    currentProject,
    loading,
    error,
    // Computed
    hasProjects,
    activeProjects,
    archivedProjects,
    // Actions
    fetchProjects,
    fetchProject,
    createProject,
    updateProject,
    deleteProject,
    uploadCoverImage,
    clearCurrentProject,
    clearError,
  }
})
