# Project-Based File Management System Design

**Date:** 2026-01-25
**Status:** Approved

## Overview

Transform Electric_RAG from a flat document system into a project-based file management system where users can organize documents into projects, search within project scope, and interact via a chat interface with source references.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| User model | Single-tenant, no auth | Internal company network use only |
| Project metadata | Rich | Name, description, system type, facility, status, tags, cover image, notes |
| Project structure | Flat with flexible search | Can search within project OR globally; simpler than hierarchical |
| Source references | Multi-reference with preview | Thumbnail cards showing source pages; best practice for RAG |
| Project home | Dashboard-style | Overview stats, recent activity, quick access |
| Search UI | Chat interface | 20% chat panel left, 80% PDF viewer right |
| Conversations | Persistent | Saved threads users can resume |
| Landing page | Global search + projects | Search across all projects, plus projects grid |

---

## Information Architecture

```
Landing Page (/)
├── Global search bar (searches all projects)
├── Projects grid (cards with metadata)
│
└── Project Page (/projects/:id)
    ├── Dashboard tab (overview, stats, recent activity)
    ├── Documents tab (upload, manage files)
    ├── Conversations tab (saved chat threads)
    │
    └── Chat Page (/projects/:id/chat/:conversationId?)
        ├── Left panel (20%): Chat interface
        │   ├── Conversation history
        │   ├── Message input
        │   └── Source reference cards (inline after AI messages)
        │
        └── Right panel (80%): PDF Viewer
            ├── Document/page selector
            ├── Zoom controls
            └── Highlighted regions (from source references)
```

**URL Structure:**
- `/` - Landing with global search
- `/projects/:id` - Project dashboard
- `/projects/:id/documents` - Document management
- `/projects/:id/conversations` - Conversation list
- `/projects/:id/chat` - New conversation
- `/projects/:id/chat/:conversationId` - Existing conversation

---

## Database Schema Changes

### New Tables

```sql
-- Projects table
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    system_type VARCHAR(100),           -- electrical, mechanical, HVAC, etc.
    facility_name VARCHAR(255),         -- plant/building name
    status VARCHAR(50) DEFAULT 'active', -- active, archived, completed
    cover_image_path VARCHAR(500),
    notes TEXT,
    tags JSONB DEFAULT '[]',            -- custom tags array
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Conversations table
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Messages table
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,          -- 'user' or 'assistant'
    content TEXT NOT NULL,
    sources JSONB,                      -- [{document_id, page_number, snippet, bbox}]
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_conversations_project_id ON conversations(project_id);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
```

### Modified Tables

```sql
-- Add project_id to documents
ALTER TABLE documents
ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE;

CREATE INDEX idx_documents_project_id ON documents(project_id);

-- Add project_id to equipment (project-scoped equipment tags)
ALTER TABLE equipment
ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE;

-- Equipment tags are unique within a project
CREATE UNIQUE INDEX idx_equipment_project_tag ON equipment(project_id, tag);
```

### Migration Strategy

1. Create a "Default Project" for existing data
2. Update all existing documents to reference the default project
3. Update all existing equipment to reference the default project
4. Make project_id NOT NULL after migration

---

## API Endpoints

### Project Endpoints

```
POST   /api/projects                      Create project
GET    /api/projects                      List all projects (with stats)
GET    /api/projects/:id                  Get project details + stats
PUT    /api/projects/:id                  Update project
DELETE /api/projects/:id                  Delete project (cascades all data)
POST   /api/projects/:id/cover-image      Upload cover image
```

### Document Endpoints (Modified)

```
POST   /api/projects/:id/documents/upload Upload to specific project
GET    /api/projects/:id/documents        List project documents
GET    /api/documents/:id                 Get document (unchanged)
DELETE /api/documents/:id                 Delete document (unchanged)
GET    /api/documents/:id/page/:num/thumbnail  Page thumbnail for previews
```

### Conversation Endpoints

```
POST   /api/projects/:id/conversations    Create conversation
GET    /api/projects/:id/conversations    List project conversations
GET    /api/conversations/:id             Get conversation with messages
PUT    /api/conversations/:id             Update conversation (title)
DELETE /api/conversations/:id             Delete conversation
```

### Message Endpoints

```
POST   /api/conversations/:id/messages    Send message, get AI response with sources
GET    /api/conversations/:id/messages    Get message history (paginated)
```

**Message Response Format:**
```json
{
  "id": 123,
  "role": "assistant",
  "content": "The VFD-101 is located on page 3 of Drawing E-101...",
  "sources": [
    {
      "document_id": 1,
      "document_name": "E-101 One Line Diagram",
      "page_number": 3,
      "snippet": "VFD-101 controls Motor M-101...",
      "bbox": {"x_min": 100, "y_min": 200, "x_max": 300, "y_max": 250},
      "equipment_tag": "VFD-101"
    }
  ],
  "created_at": "2026-01-25T10:30:00Z"
}
```

### Search Endpoints (Modified)

```
GET    /api/search?q=...&project_id=...   Search (optional project scope)
POST   /api/search/ask                    RAG query (accepts project_id in body)
GET    /api/search/global?q=...           Global search (returns project info)
```

**Global Search Response:**
```json
{
  "results": [
    {
      "document": {...},
      "page_number": 3,
      "project_id": 1,
      "project_name": "Plant A Electrical",
      "snippet": "...",
      "relevance_score": 0.95
    }
  ]
}
```

---

## Frontend Structure

### New Pages

```
views/
├── LandingView.vue              Global search + projects grid
├── ProjectDashboardView.vue     Project overview with stats
├── ProjectDocumentsView.vue     Document management within project
├── ProjectConversationsView.vue List of saved conversations
└── ProjectChatView.vue          Chat + PDF viewer split layout
```

### New Components

```
components/
├── projects/
│   ├── ProjectCard.vue          Card for projects grid
│   ├── ProjectForm.vue          Create/edit project modal
│   ├── ProjectStats.vue         Stats cards (docs, equipment, etc.)
│   └── RecentActivity.vue       Activity feed on dashboard
│
├── chat/
│   ├── ChatPanel.vue            Left 20% panel container
│   ├── ChatMessages.vue         Message list with AI responses
│   ├── ChatInput.vue            Message input with send button
│   ├── SourceCard.vue           Clickable source reference card
│   ├── SourcePreview.vue        Thumbnail preview in source card
│   └── ConversationSwitcher.vue Dropdown to switch conversations
│
├── global/
│   ├── GlobalSearchBar.vue      Search bar for landing page
│   └── GlobalSearchResults.vue  Results with project badges
│
├── conversations/
│   └── ConversationListItem.vue Item in conversations list
```

### Chat Page Layout

```
┌─────────────────────────────────────────────────────────┐
│  Project Name > Conversation Title          [Controls]  │
├────────────┬────────────────────────────────────────────┤
│            │                                            │
│  Chat      │         PDF Viewer                         │
│  Panel     │                                            │
│  (20%)     │         (80%)                              │
│            │                                            │
│ ┌────────┐ │  ┌────────────────────────────────────┐   │
│ │Message │ │  │                                    │   │
│ │History │ │  │     Document Page Image            │   │
│ │        │ │  │     (with highlight box on source) │   │
│ │  User: │ │  │                                    │   │
│ │  xxxxx │ │  └────────────────────────────────────┘   │
│ │        │ │                                            │
│ │  AI:   │ │  [◀ Prev]  Page 3 of 12  [Next ▶]        │
│ │  xxxxx │ │                                            │
│ │        │ │  [Zoom: 100%] [Fit Width] [Fit Page]      │
│ │ ┌────┐ │ │                                            │
│ │ │Src1│ │ │                                            │
│ │ └────┘ │ │                                            │
│ │ ┌────┐ │ │                                            │
│ │ │Src2│ │ │                                            │
│ │ └────┘ │ │                                            │
│ └────────┘ │                                            │
│            │                                            │
│ [________] │                                            │
│ [  Send  ] │                                            │
└────────────┴────────────────────────────────────────────┘
```

### State Management (Pinia Stores)

**New Stores:**

```typescript
// stores/projects.ts
interface ProjectsStore {
  projects: Project[]
  currentProject: Project | null
  loading: boolean
  error: string | null

  // Actions
  fetchProjects(): Promise<void>
  fetchProject(id: number): Promise<void>
  createProject(data: CreateProject): Promise<Project>
  updateProject(id: number, data: UpdateProject): Promise<void>
  deleteProject(id: number): Promise<void>
}

// stores/conversations.ts
interface ConversationsStore {
  conversations: Conversation[]
  currentConversation: Conversation | null
  messages: Message[]
  loading: boolean

  // Actions
  fetchConversations(projectId: number): Promise<void>
  createConversation(projectId: number, title?: string): Promise<Conversation>
  loadConversation(id: number): Promise<void>
  sendMessage(conversationId: number, content: string): Promise<Message>
}

// stores/chat.ts
interface ChatStore {
  pendingMessage: string
  isGenerating: boolean
  activeSource: Source | null

  // Actions
  setActiveSource(source: Source): void
  clearActiveSource(): void
}
```

**Modified Stores:**

```typescript
// stores/documents.ts
+ fetchDocuments(projectId?: number): Promise<void>
+ uploadDocument(projectId: number, file: File): Promise<void>

// stores/search.ts
+ searchScope: 'global' | 'project'
+ projectId: number | null
+ globalSearch(query: string): Promise<SearchResult[]>
```

---

## Implementation Phases

### Phase 1: Database & Backend Foundation
- Database migrations (projects, conversations, messages)
- Modify documents/equipment tables (add project_id)
- Migration script for existing data → "Default Project"
- Project CRUD API endpoints
- Update document processor for project_id
- Update document upload endpoint

### Phase 2: Project Management Frontend
- Landing page with projects grid
- Project creation/edit modal with rich metadata
- Project dashboard with stats
- Project documents page (scoped upload/list)
- Update sidebar for project context navigation
- Update router with new routes

### Phase 3: Conversations & Chat Backend
- Conversation CRUD API endpoints
- Message API with RAG integration
- Modify RAG service for project-scoped search
- Page thumbnail endpoint
- Modify search API for project scope
- Global search endpoint with project info

### Phase 4: Chat Interface Frontend
- Chat page with 20/80 split layout
- Chat panel with message history
- Source cards with thumbnail previews
- PDF viewer highlighting for source regions
- Conversation management (create, list, switch, rename)
- Global search on landing page
- Polish and testing

---

## Data Flow: Chat Interaction

```
1. User types message in ChatInput
2. chatStore.sendMessage(text) called
3. Show user message immediately (optimistic)
4. Show "AI is thinking..." indicator
5. API: POST /conversations/:id/messages
6. Backend:
   a. Save user message to DB
   b. Run RAG pipeline with project scope
   c. Generate AI response with sources
   d. Save assistant message to DB
   e. Return response with sources
7. Hide thinking indicator
8. Display AI message with inline SourceCards
9. User clicks SourceCard
10. chatStore.setActiveSource(source)
11. PDF viewer:
    a. Load document if different
    b. Navigate to page
    c. Draw highlight box on bbox coordinates
```

---

## Success Criteria

1. Users can create projects with rich metadata
2. Documents are scoped to projects
3. Search works within project or globally
4. Chat interface allows natural language questions
5. AI responses include clickable source references
6. Clicking source shows highlighted region in PDF viewer
7. Conversations are persisted and resumable
8. Existing data migrated to default project without loss
