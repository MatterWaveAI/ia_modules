import React from 'react'
import { Handle, Position } from 'reactflow'

export default function StepNode({ data }) {
  const statusColor = {
    pending: 'bg-gray-100 dark:bg-gray-800 border-gray-300 dark:border-gray-600',
    running: 'bg-blue-100 dark:bg-blue-950/50 border-blue-500 dark:border-blue-400 animate-pulse',
    completed: 'bg-green-100 dark:bg-green-950/50 border-green-500 dark:border-green-400',
    failed: 'bg-red-100 dark:bg-red-950/50 border-red-500 dark:border-red-400',
  }[data.status || 'pending']

  return (
    <>
      <Handle type="target" position={Position.Top} />
      <div className={`px-4 py-2 shadow-md rounded-lg border-2 ${statusColor} min-w-[150px]`}>
        <div className="font-bold text-sm text-gray-900 dark:text-gray-100">{data.label}</div>
        {data.duration && (
          <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">{data.duration}ms</div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </>
  )
}
