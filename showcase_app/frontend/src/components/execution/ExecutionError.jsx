import React from 'react'
import { AlertCircle } from 'lucide-react'

export default function ExecutionError({ error }) {
  if (!error) return null

  return (
    <div className="bg-red-50 dark:bg-red-950/40 border-2 border-red-200 dark:border-red-800 rounded-lg p-4">
      <div className="flex items-start space-x-3">
        <AlertCircle className="text-red-500 flex-shrink-0 mt-0.5" size={20} />
        <div className="flex-1">
          <h3 className="text-red-900 dark:text-red-300 font-semibold mb-1">Execution Failed</h3>
          <pre className="text-red-800 dark:text-red-400 text-sm whitespace-pre-wrap">{error}</pre>
        </div>
      </div>
    </div>
  )
}
