import React from 'react'
import { CheckCircle, XCircle, Clock, Circle, ChevronDown, ChevronRight } from 'lucide-react'
import { parseBackendTimestamp } from '../../lib/utils'

export default function StepsList({ steps }) {
  const [expandedSteps, setExpandedSteps] = React.useState(new Set())

  const toggleStep = (index) => {
    const newExpanded = new Set(expandedSteps)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedSteps(newExpanded)
  }

  const getStepStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={20} className="text-green-600" />
      case 'failed':
        return <XCircle size={20} className="text-red-600" />
      case 'running':
        return <Clock size={20} className="text-blue-600 animate-spin" />
      default:
        return <Circle size={20} className="text-gray-400" />
    }
  }

  const getStepStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'border-green-200 bg-green-50'
      case 'failed':
        return 'border-red-200 bg-red-50'
      case 'running':
        return 'border-blue-200 bg-blue-50'
      default:
        return 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'
    }
  }

  if (!steps || steps.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4">Execution Steps</h2>
        <p className="text-gray-600 dark:text-gray-400">No step data available</p>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-4">Execution Steps</h2>
      <div className="space-y-3">
        {steps.map((step, index) => (
          <div
            key={index}
            className={`border-2 rounded-lg p-4 ${getStepStatusColor(step.status)}`}
          >
            <div
              className="flex items-center justify-between cursor-pointer"
              onClick={() => toggleStep(index)}
            >
              <div className="flex items-center space-x-3 flex-1">
                {getStepStatusIcon(step.status)}
                <div className="flex-1">
                  <div className="font-medium">{step.step_name || `Step ${step.step_index + 1}`}</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">{step.status}</div>
                </div>
                {step.duration_ms && (
                  <div className="text-sm text-gray-600 dark:text-gray-400">{step.duration_ms}ms</div>
                )}
              </div>
              {expandedSteps.has(index) ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
            </div>

            {expandedSteps.has(index) && (
              <div className="mt-4 space-y-3 border-t pt-4">
                {step.started_at && (
                  <div>
                    <div className="text-xs font-medium text-gray-600 dark:text-gray-400">Started</div>
                    <div className="text-sm">{parseBackendTimestamp(step.started_at).toLocaleString()}</div>
                  </div>
                )}

                {step.completed_at && (
                  <div>
                    <div className="text-xs font-medium text-gray-600 dark:text-gray-400">Completed</div>
                    <div className="text-sm">{parseBackendTimestamp(step.completed_at).toLocaleString()}</div>
                  </div>
                )}

                {step.input_data && (
                  <div>
                    <div className="text-xs font-medium text-gray-600 mb-1">Input Data</div>
                    <pre className="text-xs bg-white dark:bg-gray-800 dark:text-gray-200 p-2 rounded overflow-x-auto">
                      {JSON.stringify(step.input_data, null, 2)}
                    </pre>
                  </div>
                )}

                {step.output_data && (
                  <div>
                    <div className="text-xs font-medium text-gray-600 mb-1">Output Data</div>
                    <pre className="text-xs bg-white dark:bg-gray-800 dark:text-gray-200 p-2 rounded overflow-x-auto">
                      {JSON.stringify(step.output_data, null, 2)}
                    </pre>
                  </div>
                )}

                {step.error && (
                  <div>
                    <div className="text-xs font-medium text-red-600 mb-1">Error</div>
                    <div className="text-sm text-red-700 bg-white dark:bg-gray-800 p-2 rounded">{step.error}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
