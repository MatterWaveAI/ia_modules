import React from 'react'
import { Clock, Layers } from 'lucide-react'

export default function SpanTimeline({ jobId, spans }) {
  if (!spans || spans.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
          <Layers size={20} />
          Execution Trace
        </h3>
        <div className="text-center py-12 text-gray-500">
          No telemetry spans available
        </div>
      </div>
    )
  }

  // Find the earliest and latest timestamps
  const timestamps = spans
    .flatMap(s => [s.start_time, s.end_time])
    .filter(Boolean)
    .map(t => new Date(t).getTime())
  
  const minTime = Math.min(...timestamps)
  const maxTime = Math.max(...timestamps)
  const totalDuration = maxTime - minTime

  const getPosition = (time) => {
    if (!time || totalDuration === 0) return 0
    const timeMs = new Date(time).getTime()
    return ((timeMs - minTime) / totalDuration) * 100
  }

  const getWidth = (startTime, endTime) => {
    if (!startTime || !endTime || totalDuration === 0) return 0
    const start = new Date(startTime).getTime()
    const end = new Date(endTime).getTime()
    return ((end - start) / totalDuration) * 100
  }

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'ok':
      case 'completed':
        return 'bg-green-500'
      case 'error':
      case 'failed':
        return 'bg-red-500'
      default:
        return 'bg-blue-500'
    }
  }

  // Calculate max depth for height
  const maxDepth = Math.max(...spans.map(s => s.depth || 0), 0)
  const rowHeight = 40

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <Layers size={20} />
          Execution Trace
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
          {spans.length} spans over {(totalDuration / 1000).toFixed(2)}s
        </p>
      </div>

      <div className="p-6">
        {/* Timeline ruler */}
        <div className="mb-4 relative h-8 border-b border-gray-300 dark:border-gray-600">
          <div className="absolute inset-0 flex justify-between text-xs text-gray-500">
            <span>0ms</span>
            <span>{(totalDuration / 4).toFixed(0)}ms</span>
            <span>{(totalDuration / 2).toFixed(0)}ms</span>
            <span>{((totalDuration * 3) / 4).toFixed(0)}ms</span>
            <span>{totalDuration.toFixed(0)}ms</span>
          </div>
        </div>

        {/* Span bars */}
        <div className="space-y-1" style={{ minHeight: (maxDepth + 1) * rowHeight + 'px' }}>
          {spans.map((span, idx) => {
            const left = getPosition(span.start_time)
            const width = getWidth(span.start_time, span.end_time)
            const top = (span.depth || 0) * rowHeight

            return (
              <div
                key={idx}
                className="relative"
                style={{
                  position: 'absolute',
                  top: `${top}px`,
                  left: `${left}%`,
                  width: `${width}%`,
                  minWidth: '2px'
                }}
              >
                <div
                  className={`h-8 rounded ${getStatusColor(span.status)} opacity-80 hover:opacity-100 cursor-pointer transition-opacity flex items-center px-2`}
                  title={`${span.name}\n${span.duration_ms?.toFixed(2)}ms`}
                >
                  <span className="text-white text-xs font-medium truncate">
                    {span.name}
                  </span>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                  {span.duration_ms?.toFixed(1)}ms
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
