import api from './index'
import type { SearchResponse, RAGResponse } from '@/types'

/**
 * Search for documents and equipment
 */
export async function search(query: string, limit = 10): Promise<SearchResponse> {
  const response = await api.get<SearchResponse>('/api/search', {
    params: { q: query, limit },
  })
  return response.data
}

/**
 * Ask a question using RAG (Retrieval Augmented Generation)
 */
export async function ask(
  query: string,
  limit = 5,
  includeContext = true
): Promise<RAGResponse> {
  const response = await api.post<RAGResponse>('/api/search/ask', {
    query,
    limit,
    include_context: includeContext,
  })
  return response.data
}

// Export all functions as a module
export const searchApi = {
  search,
  ask,
}

export default searchApi
