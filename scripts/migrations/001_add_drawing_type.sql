-- Migration: Add drawing_type column to pages table
-- Purpose: Support automatic classification of drawing pages

-- Add drawing_type column to pages table
ALTER TABLE pages ADD COLUMN IF NOT EXISTS drawing_type VARCHAR(50);

-- Create index for efficient filtering by drawing type
CREATE INDEX IF NOT EXISTS idx_page_drawing_type ON pages(drawing_type);

-- Valid drawing types:
-- ONE_LINE: Single-line electrical diagram (bus bars, breakers, transformers)
-- PID: Piping & Instrumentation diagram (process flow, valves, instruments)
-- CONTROL_SCHEMATIC: Control wiring diagram (relay logic, PLC I/O)
-- WIRING_DIAGRAM: Point-to-point wiring diagram (terminals, wire numbers)
-- SCHEDULE: Tabular data (panel schedules, cable schedules)
-- GENERAL: Cover sheets, notes, details, or unclassified
