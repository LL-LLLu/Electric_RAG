import api from './index'
import type { Project, ProjectDetail, ProjectCreate, ProjectUpdate } from '@/types'

/**
 * List all projects with pagination and optional status filter
 */
export async function list(
  skip = 0,
  limit = 50,
  status?: string
): Promise<Project[]> {
  const response = await api.get<Project[]>('/api/projects', {
    params: { skip, limit, status },
  })
  return response.data
}

/**
 * Get a single project by ID with stats
 */
export async function get(id: number): Promise<ProjectDetail> {
  const response = await api.get<ProjectDetail>(`/api/projects/${id}`)
  return response.data
}

/**
 * Create a new project
 */
export async function create(data: ProjectCreate): Promise<Project> {
  const response = await api.post<Project>('/api/projects', data)
  return response.data
}

/**
 * Update a project
 */
export async function update(id: number, data: ProjectUpdate): Promise<Project> {
  const response = await api.put<Project>(`/api/projects/${id}`, data)
  return response.data
}

/**
 * Delete a project
 */
export async function deleteProject(id: number): Promise<void> {
  await api.delete(`/api/projects/${id}`)
}

/**
 * Upload a cover image for a project
 */
export async function uploadCoverImage(
  id: number,
  file: File
): Promise<{ message: string; path: string }> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post<{ message: string; path: string }>(
    `/api/projects/${id}/cover-image`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  )

  return response.data
}

/**
 * Get the URL for a project cover image
 */
export function getCoverImageUrl(path: string): string {
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  return `${baseUrl}/${path}`
}

// Export all functions as a module
export const projectsApi = {
  list,
  get,
  create,
  update,
  delete: deleteProject,
  uploadCoverImage,
  getCoverImageUrl,
}

export default projectsApi
