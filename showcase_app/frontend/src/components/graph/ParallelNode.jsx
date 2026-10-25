import React from 'react'
import { Handle, Position } from 'reactflow'

export default function ParallelNode({ data }) {
  return (
    <>
      <Handle type="target" position={Position.Top} />
      <div className="px-3 py-2 bg-purple-100 dark:bg-purple-950/50 border-2 border-purple-500 dark:border-purple-400 rounded-lg shadow-md">
        <div className="font-bold text-xs text-gray-900 dark:text-gray-100">{data.label}</div>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </>
  )
}
