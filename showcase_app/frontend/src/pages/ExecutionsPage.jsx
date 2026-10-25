import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { executionAPI, hitlAPI } from '../services/api'
import { CheckCircle, XCircle, Clock, Play, Pause, ChevronDown, ChevronRight, AlertCircle, ExternalLink, Bell } from 'lucide-react'
import { useMetricsWebSocket } from '../hooks/useWebSocket'
import HITLInteractionModal from '../components/hitl/HITLInteractionModal'

export default function ExecutionsPage() {
  const queryClient = useQueryClient()
  const [selectedHITLInteraction, setSelectedHITLInteraction] = useState(null)

  const { data: executions, isLoading } = useQuery({
    queryKey: ['executions'],
    queryFn: async () => {
      const response = await executionAPI.list()
      return response.data
    },
    refetchInterval: false, // Disabled - using WebSocket instead
  })

  // Fetch all pending HITL interactions
  const { data: hitlInteractions = [] } = useQuery({
    queryKey: ['hitl-interactions'],
    queryFn: async () => {
      const response = await hitlAPI.getPending()
      return response.data
    },
    refetchInterval: 5000, // Poll every 5 seconds
  })

  // Use WebSocket for real-time updates
  const handleWebSocketUpdate = useCallback((data) => {
    // Invalidate executions list when updates come in
    queryClient.invalidateQueries(['executions'])
    queryClient.invalidateQueries(['hitl-interactions'])
  }, [queryClient])

  const { isConnected } = useMetricsWebSocket(handleWebSocketUpdate)

  // Map execution IDs to their pending interactions
  const executionHITLMap = hitlInteractions.reduce((acc, interaction) => {
    if (!acc[interaction.execution_id]) {
      acc[interaction.execution_id] = []
    }
    acc[interaction.execution_id].push(interaction)
    return acc
  }, {})

  const handleHITLResponse = async () => {
    // Refetch after HITL response
    await queryClient.invalidateQueries(['hitl-interactions'])
    await queryClient.invalidateQueries(['executions'])
    setSelectedHITLInteraction(null)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600 dark:text-gray-400">Loading executions...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Executions</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">Monitor pipeline execution history and status</p>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-800">
          <thead className="bg-gray-50 dark:bg-gray-800/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-8">
                {/* Expand column */}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Job ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Pipeline
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Progress
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Started At
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Duration
              </th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-800">
            {executions?.map((execution) => (
              <ExecutionRow
                key={execution.job_id}
                execution={execution}
                hitlInteractions={executionHITLMap[execution.job_id] || []}
                onHITLClick={setSelectedHITLInteraction}
              />
            ))}
          </tbody>
        </table>

        {(!executions || executions.length === 0) && (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            No executions yet. Run a pipeline to see results here.
          </div>
        )}
      </div>

      {/* HITL Interaction Modal */}
      {selectedHITLInteraction && (
        <HITLInteractionModal
          interaction={selectedHITLInteraction}
          onClose={() => setSelectedHITLInteraction(null)}
          onSubmit={handleHITLResponse}
        />
      )}
    </div>
  )
}

function ExecutionRow({ execution, hitlInteractions, onHITLClick }) {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)
  const hasPendingApproval = hitlInteractions.length > 0

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="text-green-500" size={20} />
      case 'failed':
        return <XCircle className="text-red-500" size={20} />
      case 'running':
        return <Play className="text-blue-500" size={20} />
      case 'paused':
      case 'waiting_for_human':
        return <Pause className="text-yellow-500" size={20} />
      default:
        return <Clock className="text-gray-500" size={20} />
    }
  }

  const getStatusBadge = (status) => {
    // If waiting for human and has pending approval, show special badge
    if ((status === 'waiting_for_human' || status === 'paused') && hasPendingApproval) {
      return (
        <button
          onClick={() => onHITLClick(hitlInteractions[0])}
          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 hover:bg-yellow-200 transition-colors cursor-pointer"
        >
          <Bell className="text-yellow-600 mr-1" size={16} />
          <span className="ml-1">Pending Approval</span>
        </button>
      )
    }

    const colors = {
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      running: 'bg-blue-100 text-blue-800',
      paused: 'bg-yellow-100 text-yellow-800',
      waiting_for_human: 'bg-yellow-100 text-yellow-800',
      pending: 'bg-gray-100 text-gray-800',
      cancelled: 'bg-gray-100 text-gray-800',
    }

    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
        {getStatusIcon(status)}
        <span className="ml-1">{status.replace('_', ' ')}</span>
      </span>
    )
  }

  const getDuration = () => {
    const start = new Date(execution.started_at)
    const end = execution.completed_at ? new Date(execution.completed_at) : new Date()
    const durationMs = end - start
    const seconds = Math.floor(durationMs / 1000)

    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    return `${minutes}m ${seconds % 60}s`
  }

  return (
    <>
      <tr className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 ${hasPendingApproval ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''}`}>
        <td className="px-6 py-4 whitespace-nowrap cursor-pointer" onClick={() => setExpanded(!expanded)}>
          {expanded ? (
            <ChevronDown className="text-gray-400" size={16} />
          ) : (
            <ChevronRight className="text-gray-400" size={16} />
          )}
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900 dark:text-gray-200">
          <button
            onClick={() => navigate(`/executions/${execution.job_id}`)}
            className="flex items-center space-x-1 hover:text-primary-600 transition"
          >
            <span>{execution.job_id.substring(0, 8)}...</span>
            <ExternalLink size={14} />
          </button>
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-200">
          {execution.pipeline_name || execution.pipeline_id?.substring(0, 8) + '...' || 'Unknown'}
        </td>
        <td className="px-6 py-4 whitespace-nowrap">
          {getStatusBadge(execution.status)}
        </td>
        <td className="px-6 py-4 whitespace-nowrap">
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className="bg-primary-600 h-2 rounded-full transition-all"
              style={{ width: `${execution.progress * 100}%` }}
            ></div>
          </div>
          <span className="text-xs text-gray-500 mt-1 block">
            {Math.round(execution.progress * 100)}%
          </span>
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          {new Date(execution.started_at).toLocaleTimeString()}
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          {getDuration()}
        </td>
      </tr>

      {expanded && (
        <tr>
          <td colSpan="7" className="px-6 py-4 bg-gray-50 dark:bg-gray-800/30">
            <ExecutionDetails execution={execution} hitlInteractions={hitlInteractions} onHITLClick={onHITLClick} />
          </td>
        </tr>
      )}
    </>
  )
}

function ExecutionDetails({ execution, hitlInteractions, onHITLClick }) {
  return (
    <div className="space-y-4">
      {/* Pending Approval Notice */}
      {hitlInteractions.length > 0 && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/40 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3">
              <Bell className="text-yellow-600 mt-0.5" size={20} />
              <div>
                <h4 className="font-semibold text-yellow-900 dark:text-yellow-200">Awaiting Human Input</h4>
                <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
                  This pipeline is paused waiting for {hitlInteractions.length} human review{hitlInteractions.length > 1 ? 's' : ''}
                </p>
                <div className="mt-2 text-sm text-yellow-800 dark:text-yellow-300">
                  <strong>Step:</strong> {hitlInteractions[0].step_name}
                </div>
                <div className="text-sm text-yellow-800 dark:text-yellow-300">
                  <strong>Prompt:</strong> {hitlInteractions[0].prompt}
                </div>
              </div>
            </div>
            <button
              onClick={() => onHITLClick(hitlInteractions[0])}
              className="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 font-semibold text-sm"
            >
              Review Now
            </button>
          </div>
        </div>
      )}

      {/* Full IDs */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
            Job ID
          </label>
          <div className="text-sm font-mono text-gray-900 dark:text-gray-200 bg-white dark:bg-gray-800 px-3 py-2 rounded border border-gray-200 dark:border-gray-700">
            {execution.job_id}
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
            Pipeline ID
          </label>
          <div className="text-sm font-mono text-gray-900 dark:text-gray-200 bg-white dark:bg-gray-800 px-3 py-2 rounded border border-gray-200 dark:border-gray-700">
            {execution.pipeline_id}
          </div>
        </div>
      </div>

      {/* Current Step */}
      {execution.current_step && (
        <div>
          <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
            Current Step
          </label>
          <div className="text-sm text-gray-900 dark:text-gray-200 bg-white dark:bg-gray-800 px-3 py-2 rounded border border-gray-200 dark:border-gray-700">
            {execution.current_step}
          </div>
        </div>
      )}

      {/* Error Message */}
      {execution.error && (
        <div>
          <label className="block text-xs font-medium text-red-500 uppercase tracking-wider mb-1 flex items-center">
            <AlertCircle size={14} className="mr-1" />
            Error
          </label>
          <div className="text-sm text-red-900 bg-red-50 px-3 py-2 rounded border border-red-200">
            {execution.error}
          </div>
        </div>
      )}

      {/* Input Data */}
      <div>
        <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
          Input Data
        </label>
        <pre className="text-xs text-gray-900 dark:text-gray-200 bg-white dark:bg-gray-800 px-3 py-2 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
          {JSON.stringify(execution.input_data, null, 2)}
        </pre>
      </div>

      {/* Output Data */}
      {execution.output_data && (
        <div>
          <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
            Output Data
          </label>
          <pre className="text-xs text-gray-900 dark:text-gray-200 bg-white dark:bg-gray-800 px-3 py-2 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto max-h-64 overflow-y-auto">
            {JSON.stringify(execution.output_data, null, 2)}
          </pre>
        </div>
      )}

      {/* Timestamps */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
            Started At
          </label>
          <div className="text-sm text-gray-900 dark:text-gray-200 bg-white dark:bg-gray-800 px-3 py-2 rounded border border-gray-200 dark:border-gray-700">
            {new Date(execution.started_at).toLocaleString()}
          </div>
        </div>
        {execution.completed_at && (
          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
              Completed At
            </label>
            <div className="text-sm text-gray-900 dark:text-gray-200 bg-white dark:bg-gray-800 px-3 py-2 rounded border border-gray-200 dark:border-gray-700">
              {new Date(execution.completed_at).toLocaleString()}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
