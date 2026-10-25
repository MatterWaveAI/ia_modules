import React from 'react'
import { Handle, Position } from 'reactflow'

export default function DecisionNode({ data }) {
  return (
    <>
      <Handle type="target" position={Position.Top} />
      <div className="relative">
        <div className="w-32 h-32 bg-yellow-100 dark:bg-yellow-950/50 border-2 border-yellow-500 dark:border-yellow-400 transform rotate-45 shadow-md">
          <div className="absolute inset-0 flex items-center justify-center transform -rotate-45">
            <span className="font-bold text-sm text-gray-900 dark:text-gray-100">{data.label}</span>
          </div>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </>
  )
}
