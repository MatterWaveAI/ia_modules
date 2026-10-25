import React from 'react'
import { Calendar, Clock } from 'lucide-react'
import { parseBackendTimestamp } from '../../lib/utils'

export default function ExecutionMetadata({ execution }) {
  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A'
    return parseBackendTimestamp(timestamp).toLocaleString()
  }

  const calculateDuration = () => {
    if (!execution.started_at) return 'N/A'
    const start = parseBackendTimestamp(execution.started_at)
    const end = execution.completed_at ? parseBackendTimestamp(execution.completed_at) : new Date()
    const seconds = Math.max(Math.floor((end - start) / 1000), 0)

    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    return `${minutes}m ${seconds % 60}s`
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <div className="flex items-center space-x-3">
          <Calendar size={24} className="text-blue-600" />
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400">Started At</p>
            <p className="font-medium">{formatTime(execution.started_at)}</p>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <div className="flex items-center space-x-3">
          <Clock size={24} className="text-green-600" />
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400">Duration</p>
            <p className="font-medium">{calculateDuration()}</p>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <div className="flex items-center space-x-3">
          <Calendar size={24} className="text-purple-600" />
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400">Completed At</p>
            <p className="font-medium">{formatTime(execution.completed_at)}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
