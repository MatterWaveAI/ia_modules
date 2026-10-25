import React from 'react'

export default function ExecutionOutput({ outputData }) {
  if (!outputData) {
    return null
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-4">Final Output</h2>
      <pre className="bg-gray-50 dark:bg-gray-800 p-4 rounded overflow-x-auto text-sm dark:text-gray-200">
        {JSON.stringify(outputData, null, 2)}
      </pre>
    </div>
  )
}
