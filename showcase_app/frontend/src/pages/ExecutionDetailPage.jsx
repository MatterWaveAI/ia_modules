import React, { useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { executionAPI, pipelinesAPI } from '../services/api'
import { useExecutionWebSocket } from '../hooks/useWebSocket'
import axios from 'axios'
import ExecutionHeader from '../components/execution/ExecutionHeader'
import ExecutionStatusCard from '../components/execution/ExecutionStatusCard'
import ExecutionError from '../components/execution/ExecutionError'
import ExecutionTimeline from '../components/execution/ExecutionTimeline'
import { /* PipelineGraphCard, */ PipelineFlowCard } from '../components/execution/PipelineGraphSection'
import SpanTimeline from '../components/telemetry/SpanTimeline'
import CheckpointList from '../components/checkpoint/CheckpointList'
import ConversationHistory from '../components/memory/ConversationHistory'
import ReplayComparison from '../components/replay/ReplayComparison'
import DecisionTimeline from '../components/decision/DecisionTimeline'
import StepDetailsList from '../components/execution/StepDetailsList'
import DataViewer from '../components/execution/DataViewer'

const API_URL = import.meta.env.VITE_API_URL || ''

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
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'completed' || s === 'failed' ? false : 1000
    },
  })

  const { data: pipeline } = useQuery({
    queryKey: ['pipeline', execution?.pipeline_id],
    queryFn: async () => {
      if (!execution?.pipeline_id) return null
      const response = await pipelinesAPI.get(execution.pipeline_id)
      return response.data
    },
    enabled: !!execution?.pipeline_id,
  })

  // Fetch telemetry spans
  const { data: telemetryData } = useQuery({
    queryKey: ['telemetry', jobId],
    queryFn: async () => {
      const response = await axios.get(`${API_URL}/api/telemetry/timeline/${jobId}`)
      return response.data
    },
    enabled: !!jobId,
    retry: false
  })

  const handleWebSocketUpdate = useCallback((data) => {
    queryClient.setQueryData(['execution', jobId], (old) => ({
      ...old,
      ...data
    }))
    // Terminal frames are partial (no progress/counts/current_step) — force a
    // final refetch so the cache reflects the canonical server state. Without
    // this, the status flip to "completed" stops the refetchInterval and the
    // derived fields stay stale (e.g. "67% / Running 1" after finish).
    if (
      data?.type === 'execution_completed' ||
      data?.type === 'execution_failed' ||
      data?.type === 'execution_paused'
    ) {
      queryClient.invalidateQueries({ queryKey: ['execution', jobId] })
    }
  }, [jobId, queryClient])

  useExecutionWebSocket(jobId, handleWebSocketUpdate)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600 dark:text-gray-400">Loading execution details...</div>
      </div>
    )
  }

  if (!execution) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-600 dark:text-red-400">Execution not found</div>
      </div>
    )
  }

  const hasSteps = execution.steps && execution.steps.length > 0
  const hasSpans = telemetryData?.timeline && telemetryData.timeline.length > 0

  return (
    <div className="space-y-4">
      <ExecutionHeader onBack={() => navigate('/executions')} />

      <section id="section-status"><ExecutionStatusCard execution={execution} /></section>
      <ExecutionError error={execution.error} />

      <section id="section-timeline"><ExecutionTimeline execution={execution} pipeline={pipeline} /></section>

      {/* <section id="section-pipeline-graph"><PipelineGraphCard pipeline={pipeline} execution={execution} /></section> */}
      <section id="section-pipeline-flow"><PipelineFlowCard execution={execution} /></section>

      {hasSpans && (
        <section id="section-trace"><SpanTimeline jobId={jobId} spans={telemetryData.timeline} /></section>
      )}

      {hasSteps && <section id="section-step-details"><StepDetailsList steps={execution.steps} /></section>}

      {execution.input_data && (
        <section id="section-input"><DataViewer title="Input Data" data={execution.input_data} /></section>
      )}
      {execution.output_data && (
        <section id="section-output">
          <DataViewer title="Final Output" data={execution.output_data} />
        </section>
      )}

      <section id="section-checkpoints"><CheckpointList jobId={jobId} /></section>
      <section id="section-conversation"><ConversationHistory sessionId={jobId} /></section>
      <section id="section-replay"><ReplayComparison jobId={jobId} /></section>
      <section id="section-decisions"><DecisionTimeline jobId={jobId} /></section>
    </div>
  )
}
