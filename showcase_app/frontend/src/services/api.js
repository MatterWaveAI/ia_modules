import axios from 'axios'
import toast from 'react-hot-toast'

// In dev, use relative URLs so Vite proxy handles routing to the backend.
// In production, use VITE_API_URL if set.
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for loading state
api.interceptors.request.use(
  (config) => {
    // Add a loading toast ID to the config for tracking
    if (config.showLoading !== false) {
      config.loadingToastId = toast.loading(config.loadingMessage || 'Loading...', {
        duration: Infinity,
      })
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    // Dismiss loading toast
    if (response.config.loadingToastId) {
      toast.dismiss(response.config.loadingToastId)
    }
    
    // Show success toast if configured
    if (response.config.successMessage) {
      toast.success(response.config.successMessage)
    }
    
    return response
  },
  (error) => {
    // Dismiss loading toast
    if (error.config?.loadingToastId) {
      toast.dismiss(error.config.loadingToastId)
    }
    
    // Show error toast with appropriate message
    const errorMessage = 
      error.response?.data?.error || 
      error.response?.data?.message || 
      error.message || 
      'An unexpected error occurred'
    
    // Don't show toast if explicitly disabled
    if (error.config?.showError !== false) {
      toast.error(errorMessage, {
        duration: 5000,
      })
    }
    
    return Promise.reject(error)
  }
)

// Pipelines
export const pipelinesAPI = {
  list: () => api.get('/pipelines'),
  get: (id) => api.get(`/pipelines/${id}`),
  create: (data) => api.post('/pipelines', data),
  update: (id, data) => api.put(`/pipelines/${id}`, data),
  delete: (id) => api.delete(`/pipelines/${id}`),
}

// Execution
export const executionAPI = {
  start: (pipelineId, inputData) =>
    api.post(`/execute/${pipelineId}`, {
      input_data: inputData,
      checkpoint_enabled: true,
    }),
  get: (jobId) => api.get(`/execute/${jobId}`),
  list: () => api.get('/execute'),
  cancel: (jobId) => api.delete(`/execute/${jobId}`),
}

// Human-in-the-Loop
export const hitlAPI = {
  getPending: (executionId, pipelineId) => {
    const params = new URLSearchParams();
    if (executionId) params.append('execution_id', executionId);
    if (pipelineId) params.append('pipeline_id', pipelineId);
    return api.get(`/hitl/pending?${params.toString()}`);
  },
  getInteraction: (interactionId) => api.get(`/hitl/${interactionId}`),
  respond: (interactionId, humanInput, respondedBy) =>
    api.post(`/hitl/${interactionId}/respond`, {
      human_input: humanInput,
      responded_by: respondedBy
    }),
  cancel: (interactionId) => api.post(`/hitl/${interactionId}/cancel`),
}

// Metrics
export const metricsAPI = {
  getReport: () => api.get('/metrics/report'),
  getSLO: () => api.get('/metrics/slo'),
  getEvents: (limit = 100) => api.get(`/metrics/events?limit=${limit}`),
  getHistory: (hours = 24) => api.get(`/metrics/history?hours=${hours}`),
}

// Telemetry
export const telemetryAPI = {
  getSpans: (jobId) => api.get(`/telemetry/spans/${jobId}`),
  getMetrics: (jobId) => api.get(`/telemetry/metrics/${jobId}`),
  getTimeline: (jobId) => api.get(`/telemetry/timeline/${jobId}`),
  getAgentMetrics: () => api.get('/telemetry/agents'),
  getLLMUsage: () => api.get('/telemetry/llm/usage'),
  getTimeseries: (metric, hours = 24) => api.get(`/telemetry/timeseries/${metric}?hours=${hours}`),
}

// Plugins
export const pluginsAPI = {
  list: () => api.get('/plugins'),
  get: (name) => api.get(`/plugins/${name}`),
  execute: (name, params) => api.post(`/plugins/${name}/execute`, { params }),
  load: (path) => api.post('/plugins/load', { path }),
  unload: (name) => api.delete(`/plugins/${name}`),
}

// Guardrails
export const guardrailsAPI = {
  listRails: () => api.get('/guardrails/rails'),
  testInput: (data) => api.post('/guardrails/test-input', data),
  testOutput: (data) => api.post('/guardrails/test-output', data),
  runPipeline: (data) => api.post('/guardrails/run', data),
}

// Collaboration Patterns
export const collaborationAPI = {
  getPatterns: () => api.get('/collaboration/patterns'),
  runConsensus: (data) => api.post('/collaboration/consensus', data, {
    loadingMessage: 'Running consensus collaboration...',
    successMessage: 'Consensus collaboration completed',
  }),
  runDebate: (data) => api.post('/collaboration/debate', data, {
    loadingMessage: 'Running debate collaboration...',
    successMessage: 'Debate collaboration completed',
  }),
  runHierarchical: (data) => api.post('/collaboration/hierarchical', data, {
    loadingMessage: 'Running hierarchical collaboration...',
    successMessage: 'Hierarchical collaboration completed',
  }),
  runPeerToPeer: (data) => api.post('/collaboration/peer-to-peer', data, {
    loadingMessage: 'Running peer-to-peer collaboration...',
    successMessage: 'Peer-to-peer collaboration completed',
  }),
  getExecutions: (pattern) => api.get('/collaboration/executions', {
    params: pattern ? { pattern } : {},
    showLoading: false,
  }),
  getExecution: (runId) => api.get(`/collaboration/executions/${runId}`),
}

// Agent Executions
export const agentExecutionsAPI = {
  list: (params) => api.get('/agents/executions', { params, showLoading: false }),
  get: (jobId) => api.get(`/agents/executions/${jobId}`, { showLoading: false }),
  getEvents: (jobId, params) => api.get(`/agents/executions/${jobId}/events`, { params, showLoading: false }),
  getSummary: (jobId) => api.get(`/agents/executions/${jobId}/summary`, { showLoading: false }),
  scan: () => api.post('/agents/executions/scan', {}, {
    loadingMessage: 'Scanning agent logs...',
    successMessage: 'Agent logs indexed',
  }),
}

// Health
export const healthAPI = {
  check: () => axios.get(`${API_BASE_URL}/health`),
}

export default api
