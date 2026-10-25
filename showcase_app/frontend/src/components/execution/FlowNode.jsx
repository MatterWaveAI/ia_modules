import React from 'react'
import { CheckCircle, XCircle, Play, Circle } from 'lucide-react'
import { parseBackendTimestamp } from '../../lib/utils'

export default function FlowNode({ step, index }) {
  const getNodeColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 border-green-400 text-green-900'
      case 'failed':
        return 'bg-red-100 border-red-400 text-red-900'
      case 'running':
        return 'bg-blue-100 border-blue-400 text-blue-900 animate-pulse'
      default:
        return 'bg-gray-100 border-gray-400 text-gray-900'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="text-green-600" size={32} />
      case 'failed':
        return <XCircle className="text-red-600" size={32} />
      case 'running':
        return <Play className="text-blue-600" size={32} />
      default:
        return <Circle className="text-gray-400" size={32} />
    }
  }

  return (
    <div className={`w-full border-2 rounded-xl p-6 ${getNodeColor(step.status)} transition-all duration-300`}>
      <div className="flex items-center space-x-4">
        {getStatusIcon(step.status)}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <div>
              <div className="text-sm font-medium opacity-75">Step {index + 1}</div>
              <h3 className="text-xl font-bold">{step.step_name}</h3>
            </div>
            {step.duration_ms != null && (
              <div className="text-right">
                <div className="text-2xl font-bold">{step.duration_ms.toFixed(0)}ms</div>
                <div className="text-xs opacity-75">duration</div>
              </div>
            )}
          </div>

          {step.error && (
            <div className="mt-2 p-3 bg-red-200 bg-opacity-50 rounded-lg">
              <div className="font-semibold text-sm">Error:</div>
              <div className="text-sm">{step.error}</div>
            </div>
          )}

          <div className="mt-2 flex items-center space-x-4 text-sm opacity-75">
            <span>Started: {parseBackendTimestamp(step.started_at).toLocaleTimeString()}</span>
            {step.completed_at && (
              <span>Completed: {parseBackendTimestamp(step.completed_at).toLocaleTimeString()}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
