import React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Clock, Play, Database, Trash2 } from 'lucide-react'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || ''

export default function CheckpointList({ jobId }) {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['checkpoints', jobId],
    queryFn: async () => {
      const response = await axios.get(`${API_URL}/api/checkpoints/${jobId}`)
      return response.data
    },
    enabled: !!jobId
  })

  const resumeMutation = useMutation({
    mutationFn: async (checkpointId) => {
      const response = await axios.post(
        `${API_URL}/api/checkpoints/checkpoint/${checkpointId}/resume`
      )
      return response.data
    },
    onSuccess: (result) => {
      // Navigate to new execution
      if (result.new_job_id) {
        window.location.href = `/executions/${result.new_job_id}`
      }
    }
  })

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-600 dark:text-gray-400">Loading checkpoints...</div>
        </div>
      </div>
    )
  }

  const checkpoints = data?.checkpoints || []

  if (checkpoints.length === 0) {
    return null
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <Database size={20} />
          Checkpoints
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
          {checkpoints.length} checkpoint{checkpoints.length !== 1 ? 's' : ''} saved
        </p>
      </div>

      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        {checkpoints.map((checkpoint) => (
          <CheckpointCard
            key={checkpoint.id}
            checkpoint={checkpoint}
            onResume={() => resumeMutation.mutate(checkpoint.id)}
            isResuming={resumeMutation.isPending}
          />
        ))}
      </div>
    </div>
  )
}

function CheckpointCard({ checkpoint, onResume, isResuming }) {
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A'
    return new Date(dateStr).toLocaleString()
  }

  const formatSize = (bytes) => {
    if (!bytes) return '0 B'
    const kb = bytes / 1024
    if (kb < 1024) return `${kb.toFixed(1)} KB`
    return `${(kb / 1024).toFixed(1)} MB`
  }

  return (
    <div className="p-6 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <div className="bg-blue-100 dark:bg-blue-900/50 p-2 rounded">
              <Database className="text-blue-600" size={20} />
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 dark:text-gray-100">{checkpoint.step_name}</h4>
              <p className="text-sm text-gray-600 dark:text-gray-400">Checkpoint ID: {checkpoint.id}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
            <div>
              <span className="text-gray-500">Created:</span>
              <span className="ml-2 text-gray-900 dark:text-gray-100">{formatDate(checkpoint.created_at)}</span>
            </div>
            <div>
              <span className="text-gray-500">State Size:</span>
              <span className="ml-2 text-gray-900 dark:text-gray-100">{formatSize(checkpoint.state_size)}</span>
            </div>
          </div>

          {checkpoint.metadata && Object.keys(checkpoint.metadata).length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100">
                View Metadata
              </summary>
              <pre className="mt-2 text-xs bg-gray-100 dark:bg-gray-800 dark:text-gray-200 p-3 rounded overflow-auto max-h-32">
                {JSON.stringify(checkpoint.metadata, null, 2)}
              </pre>
            </details>
          )}
        </div>

        <button
          onClick={onResume}
          disabled={isResuming}
          className="ml-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
        >
          <Play size={16} />
          {isResuming ? 'Resuming...' : 'Resume'}
        </button>
      </div>
    </div>
  )
}
