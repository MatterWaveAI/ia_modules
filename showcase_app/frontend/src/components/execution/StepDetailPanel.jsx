import React, { useState } from 'react'
import { CheckCircle, XCircle, Play, Clock, Activity, Code, GitCompare, FileText } from 'lucide-react'
import ReactJson from '@microlink/react-json-view'
import ReactDiffViewer from 'react-diff-viewer-continued'
import { parseBackendTimestamp } from '../../lib/utils'

export default function StepDetailPanel({ step, onClose }) {
  const [activeTab, setActiveTab] = useState('overview')

  const getStepIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="text-green-500" size={24} />
      case 'failed':
        return <XCircle className="text-red-500" size={24} />
      case 'running':
        return <Play className="text-blue-500 animate-pulse" size={24} />
      default:
        return <Clock className="text-gray-400" size={24} />
    }
  }

  const getStatusBadge = (status) => {
    const colors = {
      completed: 'bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300 border-green-300 dark:border-green-700',
      failed: 'bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300 border-red-300 dark:border-red-700',
      running: 'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300 border-blue-300 dark:border-blue-700',
      pending: 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-300 border-gray-300 dark:border-gray-600',
    }

    return (
      <span className={`px-3 py-1 rounded-full text-sm font-medium border ${colors[status] || colors.pending}`}>
        {status?.charAt(0).toUpperCase() + status?.slice(1)}
      </span>
    )
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'input', label: 'Input', icon: Code },
    { id: 'output', label: 'Output', icon: Code },
    { id: 'diff', label: 'Diff', icon: GitCompare },
    { id: 'logs', label: 'Logs', icon: FileText },
  ]

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="border-b dark:border-gray-700 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {getStepIcon(step.status)}
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{step.step_name}</h2>
              <div className="flex items-center gap-3 mt-1">
                {getStatusBadge(step.status)}
                {step.duration_ms != null && (
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Duration: {step.duration_ms.toFixed(0)}ms
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-2xl font-bold"
          >
            ×
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b dark:border-gray-700 px-6">
          <div className="flex gap-1">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors ${
                    activeTab === tab.id
                      ? 'text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'
                  }`}
                >
                  <Icon size={18} />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'overview' && <OverviewTab step={step} />}
          {activeTab === 'input' && <JsonTab data={step.input_data} title="Input Data" />}
          {activeTab === 'output' && <JsonTab data={step.output_data} title="Output Data" />}
          {activeTab === 'diff' && <DiffTab step={step} />}
          {activeTab === 'logs' && <LogsTab logs={step.logs} />}
        </div>
      </div>
    </div>
  )
}

function OverviewTab({ step }) {
  const metrics = [
    {
      label: 'Duration',
      value: step.duration_ms != null ? `${step.duration_ms.toFixed(2)}ms` : 'N/A',
      icon: Clock,
    },
    {
      label: 'Status',
      value: step.status || 'Unknown',
      icon: Activity,
    },
    {
      label: 'Retry Count',
      value: step.retry_count || 0,
      icon: Activity,
    },
  ]

  // Add tokens if available
  if (step.tokens) {
    metrics.push({
      label: 'Tokens Used',
      value: step.tokens,
      icon: Code,
    })
  }

  // Add cost if available
  if (step.cost != null) {
    metrics.push({
      label: 'Cost',
      value: `$${step.cost.toFixed(4)}`,
      icon: Activity,
    })
  }

  return (
    <div className="space-y-6">
      {/* Error Display */}
      {step.error && (
        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <h3 className="text-red-900 dark:text-red-300 font-semibold mb-2">Error Details</h3>
          <p className="text-red-800 dark:text-red-400 font-mono text-sm whitespace-pre-wrap">{step.error}</p>
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {metrics.map((metric, idx) => {
          const Icon = metric.icon
          return (
            <div key={idx} className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400 text-sm mb-1">
                <Icon size={16} />
                {metric.label}
              </div>
              <div className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{metric.value}</div>
            </div>
          )
        })}
      </div>

      {/* Timestamps */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Execution Timeline</h3>
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-2">
          {step.started_at && (
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Started:</span>
              <span className="font-mono text-gray-900 dark:text-gray-100">
                {parseBackendTimestamp(step.started_at).toLocaleString()}
              </span>
            </div>
          )}
          {step.completed_at && (
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Completed:</span>
              <span className="font-mono text-gray-900 dark:text-gray-100">
                {parseBackendTimestamp(step.completed_at).toLocaleString()}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Metadata */}
      {step.metadata && Object.keys(step.metadata).length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Metadata</h3>
          <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
            <ReactJson
              src={step.metadata}
              theme="rjv-default"
              collapsed={false}
              displayDataTypes={false}
              enableClipboard={true}
              displayObjectSize={false}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function JsonTab({ data, title }) {
  if (!data || (typeof data === 'object' && Object.keys(data).length === 0)) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        No {title.toLowerCase()} available
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
        <button
          onClick={() => {
            navigator.clipboard.writeText(JSON.stringify(data, null, 2))
          }}
          className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded border border-gray-300 dark:border-gray-600"
        >
          Copy JSON
        </button>
      </div>
      <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700 p-4 overflow-auto max-h-[600px]">
        <ReactJson
          src={data}
          theme="rjv-default"
          collapsed={2}
          displayDataTypes={false}
          enableClipboard={true}
          displayObjectSize={true}
          name={null}
        />
      </div>
    </div>
  )
}

function DiffTab({ step }) {
  const oldValue = JSON.stringify(step.input_data || {}, null, 2)
  const newValue = JSON.stringify(step.output_data || {}, null, 2)

  if (!step.input_data && !step.output_data) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        No data available for comparison
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Input vs Output Comparison</h3>
      <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
        <ReactDiffViewer
          oldValue={oldValue}
          newValue={newValue}
          splitView={true}
          useDarkTheme={false}
          leftTitle="Input Data"
          rightTitle="Output Data"
          showDiffOnly={false}
        />
      </div>
    </div>
  )
}

function LogsTab({ logs }) {
  if (!logs || logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        No logs available
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Execution Logs</h3>
      <div className="bg-gray-900 rounded-lg p-4 overflow-auto max-h-[600px] font-mono text-sm">
        {logs.map((log, idx) => (
          <div key={idx} className="text-gray-300 hover:bg-gray-800 px-2 py-1 rounded">
            <span className="text-gray-500">[{log.timestamp || idx}]</span>{' '}
            <span className={getLogLevelColor(log.level)}>{log.level || 'INFO'}</span>:{' '}
            {log.message}
          </div>
        ))}
      </div>
    </div>
  )
}

function getLogLevelColor(level) {
  switch (level?.toLowerCase()) {
    case 'error':
      return 'text-red-400'
    case 'warn':
    case 'warning':
      return 'text-yellow-400'
    case 'info':
      return 'text-blue-400'
    case 'debug':
      return 'text-gray-400'
    default:
      return 'text-gray-300'
  }
}
