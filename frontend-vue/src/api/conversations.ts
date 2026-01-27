import api from './index'
import type {
  Conversation,
  ConversationDetail,
  ConversationCreate,
  Message,
  MessageCreate,
} from '@/types'

/**
 * List all conversations for a project
 */
export async function listByProject(
  projectId: number,
  skip = 0,
  limit = 50
): Promise<Conversation[]> {
  const response = await api.get<Conversation[]>(
    `/api/projects/${projectId}/conversations`,
    { params: { skip, limit } }
  )
  return response.data
}

/**
 * Create a new conversation in a project
 */
export async function create(
  projectId: number,
  data: ConversationCreate = {}
): Promise<Conversation> {
  const response = await api.post<Conversation>(
    `/api/projects/${projectId}/conversations`,
    data
  )
  return response.data
}

/**
 * Get a conversation with all messages
 */
export async function get(conversationId: number): Promise<ConversationDetail> {
  const response = await api.get<ConversationDetail>(
    `/api/conversations/${conversationId}`
  )
  return response.data
}

/**
 * Update conversation title
 */
export async function update(
  conversationId: number,
  data: { title?: string }
): Promise<Conversation> {
  const response = await api.put<Conversation>(
    `/api/conversations/${conversationId}`,
    data
  )
  return response.data
}

/**
 * Delete a conversation
 */
export async function deleteConversation(conversationId: number): Promise<void> {
  await api.delete(`/api/conversations/${conversationId}`)
}

/**
 * Send a message and get AI response
 */
export async function sendMessage(
  conversationId: number,
  data: MessageCreate
): Promise<Message> {
  const response = await api.post<Message>(
    `/api/conversations/${conversationId}/messages`,
    data
  )
  return response.data
}

/**
 * Get paginated message history
 */
export async function getMessages(
  conversationId: number,
  skip = 0,
  limit = 100
): Promise<Message[]> {
  const response = await api.get<Message[]>(
    `/api/conversations/${conversationId}/messages`,
    { params: { skip, limit } }
  )
  return response.data
}

// Export all functions as a module
export const conversationsApi = {
  listByProject,
  create,
  get,
  update,
  delete: deleteConversation,
  sendMessage,
  getMessages,
}

export default conversationsApi
