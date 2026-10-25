/**
 * Multi-Agent Type Definitions
 * 
 * Shared TypeScript types for multi-agent components
 */

export interface Workflow {
  workflow_id: string;
  status: string;
  agent_count: number;
  edge_count: number;
  created_at: string;
  mermaid_diagram?: string;
}

export interface AgentStats {
  executions: number;
  total_duration: number;
  average_duration?: number;
  iterations?: number[];
}

export interface WorkflowState {
  workflow_id: string;
  status: string;
  agent_stats: Record<string, AgentStats>;
  current_state: any;
  execution_count: number;
  last_execution: string | null;
}

export interface Communication {
  timestamp: string;
  type: 'agent_activated' | 'agent_completed' | 'message';
  agent: string;
  data: any;
  duration?: number;
}

export interface Template {
  name: string;
  description: string;
  agents: AgentConfig[];
  edges: EdgeConfig[];
  feedback_loops?: FeedbackLoopConfig[];
}

export interface AgentConfig {
  id: string;
  role: string;
  description: string;
}

export interface EdgeConfig {
  from: string;
  to: string;
  condition?: string;
  metadata?: Record<string, any>;
}

export interface FeedbackLoopConfig {
  from: string;
  to: string;
  max_iterations: number;
}

export interface ExecutionRequest {
  start_agent: string;
  initial_data: Record<string, any>;
}

export interface ExecutionResult {
  execution_id: string;
  workflow_id: string;
  status: string;
  result: any;
  communications: Communication[];
  agent_stats: Record<string, AgentStats>;
}
