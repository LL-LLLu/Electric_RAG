import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig, type AxiosResponse } from 'axios'

// Create axios instance with default config
const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 120000, // 2 minutes
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Log requests in development
    if (import.meta.env.DEV) {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`, config.params || '')
    }
    return config
  },
  (error: AxiosError) => {
    console.error('[API] Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response: AxiosResponse) => {
    // Log responses in development
    if (import.meta.env.DEV) {
      console.log(`[API] Response ${response.status}:`, response.config.url)
    }
    return response
  },
  (error: AxiosError) => {
    // Handle common error cases
    if (error.response) {
      // Server responded with error status
      const status = error.response.status
      const message = (error.response.data as { detail?: string })?.detail || error.message

      switch (status) {
        case 400:
          console.error('[API] Bad request:', message)
          break
        case 404:
          console.error('[API] Not found:', message)
          break
        case 422:
          console.error('[API] Validation error:', message)
          break
        case 500:
          console.error('[API] Server error:', message)
          break
        default:
          console.error(`[API] Error ${status}:`, message)
      }
    } else if (error.request) {
      // Request was made but no response received
      console.error('[API] Network error: No response received')
    } else {
      // Error in request configuration
      console.error('[API] Request configuration error:', error.message)
    }

    return Promise.reject(error)
  }
)

export default api

// Export types for use in other modules
export type { AxiosError, AxiosResponse }
