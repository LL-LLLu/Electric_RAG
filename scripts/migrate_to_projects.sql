-- Migration script: Add project support to Electric_RAG
-- Run with: psql -d electrical_rag -f scripts/migrate_to_projects.sql

-- 1. Create projects table
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    system_type VARCHAR(100),
    facility_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    cover_image_path VARCHAR(500),
    notes TEXT,
    tags TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. Create conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversation_project ON conversations(project_id);

-- 3. Create messages table
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sources TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_conversation ON messages(conversation_id);

-- 4. Add project_id to documents (nullable first for migration)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE;

-- 5. Add project_id to equipment (nullable first for migration)
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE;

-- 6. Create default project for existing data
INSERT INTO projects (name, description, status, created_at, updated_at)
SELECT 'Default Project', 'Auto-created project for existing documents', 'active', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM projects WHERE name = 'Default Project');

-- 7. Migrate existing documents to default project
UPDATE documents
SET project_id = (SELECT id FROM projects WHERE name = 'Default Project' LIMIT 1)
WHERE project_id IS NULL;

-- 8. Migrate existing equipment to default project
UPDATE equipment
SET project_id = (SELECT id FROM projects WHERE name = 'Default Project' LIMIT 1)
WHERE project_id IS NULL;

-- 9. Create indexes
CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_equipment_project_id ON equipment(project_id);

-- 10. Drop old unique constraint on equipment.tag and add project-scoped one
-- First check if the old constraint exists and drop it
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'equipment_tag_key') THEN
        ALTER TABLE equipment DROP CONSTRAINT equipment_tag_key;
    END IF;
END $$;

-- Create new project-scoped unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_equipment_project_tag ON equipment(project_id, tag);

-- Done!
SELECT 'Migration complete. Default project created with ID: ' || id FROM projects WHERE name = 'Default Project';
