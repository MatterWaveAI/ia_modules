-- Human-in-the-Loop (HITL) Database Schema
-- Supports pausing pipeline execution and collecting human input

-- Pipeline states for paused executions
CREATE TABLE IF NOT EXISTS hitl_interactions (
    interaction_id VARCHAR(255) PRIMARY KEY,
    execution_id VARCHAR(255) NOT NULL,
    pipeline_id VARCHAR(255) NOT NULL,
    step_id VARCHAR(255) NOT NULL,
    step_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'expired', 'cancelled')),

    -- UI Schema for rendering interaction form
    ui_schema TEXT,  -- JSON

    -- Context data for the interaction
    prompt TEXT,
    context_data TEXT,  -- JSON - data available to the step

    -- Response data
    human_input TEXT,  -- JSON - user's response
    responded_by VARCHAR(255),  -- user ID who responded

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (execution_id) REFERENCES pipeline_executions(execution_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_hitl_execution ON hitl_interactions(execution_id);
CREATE INDEX IF NOT EXISTS idx_hitl_status ON hitl_interactions(status);
CREATE INDEX IF NOT EXISTS idx_hitl_expires ON hitl_interactions(expires_at);
CREATE INDEX IF NOT EXISTS idx_hitl_created ON hitl_interactions(created_at);

-- User assignments for interactions (optional - for role-based assignment)
CREATE TABLE IF NOT EXISTS hitl_assignments (
    id SERIAL PRIMARY KEY,
    interaction_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    role VARCHAR(100) DEFAULT 'reviewer',
    assigned_at TIMESTAMP DEFAULT NOW(),
    notified BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (interaction_id) REFERENCES hitl_interactions(interaction_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hitl_assignments_user ON hitl_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_hitl_assignments_interaction ON hitl_assignments(interaction_id);
