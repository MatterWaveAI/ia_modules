import React from 'react'
import ExecutionHeader from '../execution/ExecutionHeader'
import ExecutionStatusCard from '../execution/ExecutionStatusCard'
import ExecutionError from '../execution/ExecutionError'
import ExecutionTimeline from '../execution/ExecutionTimeline'
import PipelineGraphSection from '../execution/PipelineGraphSection'
import SpanTimeline from '../telemetry/SpanTimeline'
import CheckpointList from '../checkpoint/CheckpointList'
import ConversationHistory from '../memory/ConversationHistory'
import ReplayComparison from '../replay/ReplayComparison'
import DecisionTimeline from '../decision/DecisionTimeline'
import StepDetailsList from '../execution/StepDetailsList'
import DataViewer from '../execution/DataViewer'

// Component registry - maps component types to actual components
const componentRegistry = {
  ExecutionHeader,
  ExecutionStatusCard,
  ExecutionError,
  ExecutionTimeline,
  PipelineGraphSection,
  SpanTimeline,
  CheckpointList,
  ConversationHistory,
  ReplayComparison,
  DecisionTimeline,
  StepDetailsList,
  DataViewer,
  // New pipeline step components (to be implemented)
  AgentStep: ({ step }) => (
    <div className="p-4">
      <h4 className="font-semibold text-purple-700">🤖 Agent Step</h4>
      <p className="text-sm text-gray-600 mt-1">
        {step?.name || 'AI Agent execution step'}
      </p>
      {step?.config && (
        <div className="mt-2 text-xs text-gray-500">
          <strong>Config:</strong> {JSON.stringify(step.config, null, 2)}
        </div>
      )}
    </div>
  ),
  LLMCallStep: ({ step }) => (
    <div className="p-4">
      <h4 className="font-semibold text-blue-700">🧠 LLM Call Step</h4>
      <p className="text-sm text-gray-600 mt-1">
        {step?.name || 'Large Language Model call'}
      </p>
      {step?.config && (
        <div className="mt-2 text-xs text-gray-500">
          <strong>Config:</strong> {JSON.stringify(step.config, null, 2)}
        </div>
      )}
    </div>
  ),
  GuardrailsStep: ({ step }) => (
    <div className="p-4">
      <h4 className="font-semibold text-red-700">🛡️ Guardrails Step</h4>
      <p className="text-sm text-gray-600 mt-1">
        {step?.name || 'Safety and validation checks'}
      </p>
      {step?.config && (
        <div className="mt-2 text-xs text-gray-500">
          <strong>Config:</strong> {JSON.stringify(step.config, null, 2)}
        </div>
      )}
    </div>
  ),
  ToolUseStep: ({ step }) => (
    <div className="p-4">
      <h4 className="font-semibold text-green-700">🔧 Tool Use Step</h4>
      <p className="text-sm text-gray-600 mt-1">
        {step?.name || 'Tool execution and integration'}
      </p>
      {step?.config && (
        <div className="mt-2 text-xs text-gray-500">
          <strong>Config:</strong> {JSON.stringify(step.config, null, 2)}
        </div>
      )}
    </div>
  ),
}

// Draggable wrapper for execution components
export function DraggableExecutionHeader({ execution, onBack, ...props }) {
  return <ExecutionHeader onBack={onBack} />
}

export function DraggableExecutionStatusCard({ execution, ...props }) {
  return <ExecutionStatusCard execution={execution} />
}

export function DraggableExecutionError({ error, ...props }) {
  return <ExecutionError error={error} />
}

export function DraggableExecutionTimeline({ execution, ...props }) {
  return <ExecutionTimeline execution={execution} />
}

export function DraggablePipelineGraphSection({ pipeline, execution, ...props }) {
  return <PipelineGraphSection pipeline={pipeline} execution={execution} />
}

export function DraggableSpanTimeline({ jobId, spans, ...props }) {
  return <SpanTimeline jobId={jobId} spans={spans} />
}

export function DraggableCheckpointList({ jobId, ...props }) {
  return <CheckpointList jobId={jobId} />
}

export function DraggableConversationHistory({ sessionId, ...props }) {
  return <ConversationHistory sessionId={sessionId} />
}

export function DraggableReplayComparison({ jobId, ...props }) {
  return <ReplayComparison jobId={jobId} />
}

export function DraggableDecisionTimeline({ jobId, ...props }) {
  return <DecisionTimeline jobId={jobId} />
}

export function DraggableStepDetailsList({ steps, ...props }) {
  return <StepDetailsList steps={steps} />
}

export function DraggableDataViewer({ title, data, maxHeight, ...props }) {
  return <DataViewer title={title} data={data} maxHeight={maxHeight} />
}

// Generic component renderer that uses the registry
export function ComponentRenderer({
  componentType,
  itemId,
  execution,
  pipeline,
  jobId,
  telemetryData,
  ...componentProps
}) {
  const Component = componentRegistry[componentType]

  if (!Component) {
    return (
      <div className="p-4 border border-dashed border-gray-300 rounded">
        <h4 className="font-semibold text-gray-700">Unknown Component</h4>
        <p className="text-sm text-gray-500 mt-1">
          Component type: {componentType}
        </p>
      </div>
    )
  }

  // Merge execution context with component props
  const mergedProps = {
    ...componentProps,
    // Override with execution context where appropriate
    execution: componentProps.execution || execution,
    pipeline: componentProps.pipeline || pipeline,
    jobId: componentProps.jobId || jobId,
    telemetryData: componentProps.telemetryData || telemetryData,
    // For step components, merge step data
    ...(componentProps.step && {
      step: {
        ...componentProps.step,
        // Could add execution context to step if needed
      }
    })
  }

  return <Component {...mergedProps} />
}

export { componentRegistry }