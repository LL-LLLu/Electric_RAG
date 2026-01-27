-- Add detailed_connections table for rich connection metadata from multi-agent AI analysis

CREATE TABLE IF NOT EXISTS detailed_connections (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    source_tag VARCHAR(100) NOT NULL,
    target_tag VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,  -- ELECTRICAL, CONTROL, MECHANICAL, INTERLOCK
    connection_type VARCHAR(50),     -- FEEDS, CONTROLS, PIPE, DUCT, DRIVES, etc.

    -- Electrical details
    voltage VARCHAR(50),
    breaker VARCHAR(100),
    wire_size VARCHAR(50),
    wire_numbers TEXT,  -- JSON array
    load VARCHAR(100),

    -- Control details
    signal_type VARCHAR(50),  -- 4-20mA, 0-10V, 24VDC, dry contact
    io_type VARCHAR(20),      -- AI, AO, DI, DO
    point_name VARCHAR(100),
    function TEXT,

    -- Mechanical details
    medium VARCHAR(100),      -- CHW, HW, steam, air, etc.
    pipe_size VARCHAR(50),
    pipe_spec VARCHAR(100),
    inline_devices TEXT,      -- JSON array of valves/dampers

    -- General
    details_json TEXT,        -- Full details as JSON for flexibility
    confidence FLOAT DEFAULT 0.7,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_detailed_conn_doc_page ON detailed_connections(document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_detailed_conn_source ON detailed_connections(source_tag);
CREATE INDEX IF NOT EXISTS idx_detailed_conn_target ON detailed_connections(target_tag);
CREATE INDEX IF NOT EXISTS idx_detailed_conn_category ON detailed_connections(category);
