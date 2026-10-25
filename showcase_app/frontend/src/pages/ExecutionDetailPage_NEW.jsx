import React, { useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { executionAPI, pipelinesAPI } from '../services/api'
import { useExecutionWebSocket } from '../hooks/useWebSocket'
import ExecutionHeader from '../components/execution/ExecutionHeader'
import ExecutionStatusCard from '../components/execution/ExecutionStatusCard'
import ExecutionMetadata from '../components/execution/ExecutionMetadata'
import PipelineGraph from '../components/PipelineGraph'
import StepsList from '../components/execution/StepsList'
import ExecutionOutput from '../components/execution/ExecutionOutput'

export default function ExecutionDetailPage() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: execution, isLoading } = useQuery({
    queryKey: ['execution', jobId],
    queryFn: async () => {
      const response = await executionAPI.get(jobId)
      return response.data
    },
    refetchInterval: false, // Using WebSocket instead
  })

  // Fetch pipeline details for graph visualization
  const { data: pipeline } = useQuery({
    queryKey: ['pipeline', execution?.pipeline_id],
    queryFn: async () => {
      if (!execution?.pipeline_id) return null
      const response = await pipelinesAPI.get(execution.pipeline_id)
      return response.data
    },
    enabled: !!execution?.pipeline_id,
  })

  // WebSocket for real-time updates
  const handleWebSocketUpdate = useCallback((data) => {
    queryClient.setQueryData(['execution', jobId], (old) => ({
      ...old,
      ...data
    }))
  }, [jobId, queryClient])

  useExecutionWebSocket(jobId, handleWebSocketUpdate)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600">Loading execution details...</div>
      </div>
    )
  }

  if (!execution) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-600">Execution not found</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <ExecutionHeader onBack={() => navigate('/executions')} />
      <ExecutionStatusCard execution={execution} />
      <ExecutionMetadata execution={execution} />

      {pipeline && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Pipeline Flow</h2>
          <PipelineGraph pipeline={pipeline} execution={execution} />
        </div>
      )}

      <StepsList steps={execution.steps} />
      <ExecutionOutput outputData={execution.output_data} />
    </div>
  )
}
