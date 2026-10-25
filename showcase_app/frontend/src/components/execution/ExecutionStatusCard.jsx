import React from 'react'
import { CheckCircle, XCircle, Clock, Play, AlertCircle } from 'lucide-react'
import { parseBackendTimestamp } from '../../lib/utils'

export default function ExecutionStatusCard({ execution }) {
  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={24} className="text-green-500" />
      case 'failed':
        return <XCircle size={24} className="text-red-500" />
      case 'running':
        return <Play size={24} className="text-blue-500 animate-pulse" />
      case 'pending':
        return <Clock size={24} className="text-yellow-600 dark:text-yellow-400" />
      default:
        return <AlertCircle size={24} className="text-gray-500" />
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-950/40 border-green-300 dark:border-green-800'
      case 'failed':
        return 'text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-950/40 border-red-300 dark:border-red-800'
      case 'running':
        return 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/40 border-blue-300 dark:border-blue-800'
      case 'pending':
        return 'text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-950/40 border-yellow-300 dark:border-yellow-800'
      default:
        return 'text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700'
    }
  }

  const getDuration = () => {
    // Backend emits naive ISO strings (tzinfo stripped) for UTC timestamps.
    // new Date(naiveIso) parses as local time in most browsers, so we append
    // 'Z' when there's no timezone suffix to force UTC interpretation.
    const start = parseBackendTimestamp(execution.started_at)
    const end = execution.completed_at ? parseBackendTimestamp(execution.completed_at) : new Date()
    const durationMs = Math.max(end - start, 0)
    const seconds = Math.floor(durationMs / 1000)

    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    return `${minutes}m ${seconds % 60}s`
  }

  return (
    <div className={`border-2 rounded-lg p-6 ${getStatusColor(execution.status)}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          {getStatusIcon(execution.status)}
          <div>
            <h1 className="text-2xl font-bold">
              {execution.pipeline_name || 'Pipeline Execution'}
            </h1>
            <p className="text-sm opacity-75 font-mono">{execution.job_id}</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold">{Math.round(execution.progress * 100)}%</div>
          <div className="text-sm opacity-75">{execution.status}</div>
        </div>
      </div>

      {execution.current_step && (
        <div className="mt-4 flex items-center space-x-2">
          <Play size={16} className="animate-pulse" />
          <span className="text-sm font-medium">Currently executing: {execution.current_step}</span>
        </div>
      )}

      <div className="mt-4">
        <div className="w-full bg-white/30 dark:bg-black/20 rounded-full h-3">
          <div
            className="bg-current h-3 rounded-full transition-all duration-300"
            style={{ width: `${execution.progress * 100}%` }}
          ></div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm flex-wrap gap-2">
        <span>Started: {parseBackendTimestamp(execution.started_at).toLocaleString()}</span>
        <span>Duration: {getDuration()}</span>
        {execution.completed_at && (
          <span>Completed: {parseBackendTimestamp(execution.completed_at).toLocaleString()}</span>
        )}
      </div>
    </div>
  )
}
