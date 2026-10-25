import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { pipelinesAPI, executionAPI } from '../services/api'
import { Play, FileCode, Tag, Calendar, X, Inbox, Edit, LayoutGrid, Table as TableIcon } from 'lucide-react'
import { LoadingSpinner, ButtonSpinner } from '../components/ui/spinner'
import { SkeletonCard } from '../components/ui/skeleton'
import { EmptyState } from '../components/ui/empty-state'
import { useToast } from '../hooks/useToast'

// Hardcoded test data for pipelines that require input
const DEFAULT_INPUTS = {
  'Simple Three-Step Pipeline': {
    topic: 'artificial intelligence',
  },
  'Conditional Processing Pipeline': {
    threshold: 0.8,
    test_data: [
      { quality_score: 0.95, content: 'high quality data 1' },
      { quality_score: 0.88, content: 'high quality data 2' },
      { quality_score: 0.92, content: 'high quality data 3' },
      { quality_score: 0.65, content: 'low quality data 1' },
      { quality_score: 0.45, content: 'low quality data 2' },
    ],
  },
  'Parallel Data Processing Pipeline': {
    loaded_data: [
      { id: 1, value: 'test data 1' },
      { id: 2, value: 'test data 2' },
      { id: 3, value: 'test data 3' },
      { id: 4, value: 'test data 4' },
      { id: 5, value: 'test data 5' },
      { id: 6, value: 'test data 6' },
    ],
  },
  'Iterative Content Generation Pipeline': {
    topic: 'machine learning',
    max_revisions: 3,
  },
  'Agent-Based Processing Pipeline': {
    task: 'Analyze the provided content and extract key insights',
    content: 'The quick brown fox jumps over the lazy dog. This is sample content for agent analysis.',
  },
  'Human-in-the-Loop Test Pipeline': {},
}

// Build a { paramName: defaultValue } object from a pipeline's declared
// parameters, preferring any hardcoded DEFAULT_INPUTS override for that pipeline
// so the form pre-populates with realistic sample data.
function buildInitialFormValues(pipeline) {
  const params = pipeline?.config?.parameters || []
  const overrides = DEFAULT_INPUTS[pipeline?.name] || {}
  const values = {}
  for (const p of params) {
    if (!p?.name) continue
    if (p.name in overrides) {
      values[p.name] = overrides[p.name]
    } else {
      values[p.name] = defaultForSchema(p.schema)
    }
  }
  // Preserve any override keys that aren't declared as parameters (legacy shapes).
  for (const [k, v] of Object.entries(overrides)) {
    if (!(k in values)) values[k] = v
  }
  return values
}

function defaultForSchema(schema) {
  const t = schema?.type
  if (t === 'number' || t === 'integer') return 0
  if (t === 'boolean') return false
  if (t === 'array') return []
  if (t === 'object') return {}
  return ''
}

export default function PipelinesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [executionDialog, setExecutionDialog] = useState(null)
  const [formValues, setFormValues] = useState({})
  const [inputData, setInputData] = useState('')
  const [inputMode, setInputMode] = useState('form') // 'form' | 'json'
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('pipelinesViewMode') || 'table')

  const handleViewModeChange = (mode) => {
    setViewMode(mode)
    localStorage.setItem('pipelinesViewMode', mode)
  }

  const { data: pipelines, isLoading, error } = useQuery({
    queryKey: ['pipelines'],
    queryFn: async () => {
      const response = await pipelinesAPI.list()
      return response.data
    },
  })

  const executeMutation = useMutation({
    mutationFn: async ({ pipelineId, inputData }) => {
      const response = await executionAPI.start(pipelineId, inputData || {})
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries(['executions'])
      setExecutionDialog(null)
      toast.success(`Pipeline execution started! Job ID: ${data.job_id}`)
      navigate(`/executions/${data.job_id}`)
    },
    onError: (error) => {
      toast.error(`Failed to start pipeline: ${error.message}`)
    },
  })

  const handleExecute = (pipeline) => {
    const initial = buildInitialFormValues(pipeline)
    setFormValues(initial)
    setInputData(JSON.stringify(initial, null, 2))
    setInputMode('form')
    setExecutionDialog(pipeline)
  }

  // Keep form <-> JSON views in sync when the user toggles between them.
  const switchInputMode = (nextMode) => {
    if (nextMode === inputMode) return
    if (nextMode === 'json') {
      setInputData(JSON.stringify(formValues, null, 2))
    } else {
      try {
        const parsed = JSON.parse(inputData)
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          setFormValues(parsed)
        }
      } catch {
        // Keep the last good form values if JSON is currently invalid.
      }
    }
    setInputMode(nextMode)
  }

  const handleFormFieldChange = (name, value) => {
    setFormValues((prev) => ({ ...prev, [name]: value }))
  }

  const handleConfirmExecution = () => {
    let parsedInput
    if (inputMode === 'json') {
      try {
        parsedInput = JSON.parse(inputData)
      } catch (e) {
        console.error('JSON parse error:', e)
        toast.error(`Invalid JSON input: ${e.message}`)
        return
      }
    } else {
      parsedInput = formValues
    }
    console.log('Executing pipeline:', executionDialog.id, 'with input:', parsedInput)
    executeMutation.mutate({ pipelineId: executionDialog.id, inputData: parsedInput })
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Pipelines</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Manage and execute your pipelines</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Pipelines</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Manage and execute your pipelines</p>
        </div>
        <EmptyState
          icon={FileCode}
          title="Failed to load pipelines"
          description={error.message || "We couldn't load your pipelines. Please try again."}
          action={() => window.location.reload()}
          actionLabel="Retry"
        />
      </div>
    )
  }

  if (!pipelines || pipelines.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Pipelines</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Manage and execute your pipelines</p>
        </div>
        <EmptyState
          icon={Inbox}
          title="No pipelines yet"
          description="Create your first pipeline to get started with IA Modules."
          action={() => navigate('/editor')}
          actionLabel="Create Pipeline"
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Pipelines</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Manage and execute your pipelines</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="inline-flex rounded-lg border border-gray-300 dark:border-gray-600 overflow-hidden" role="group" aria-label="View mode">
            <button
              type="button"
              onClick={() => handleViewModeChange('table')}
              aria-pressed={viewMode === 'table'}
              className={`px-3 py-2 flex items-center gap-2 text-sm transition ${
                viewMode === 'table'
                  ? 'bg-primary-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
            >
              <TableIcon size={16} />
              Table
            </button>
            <button
              type="button"
              onClick={() => handleViewModeChange('cards')}
              aria-pressed={viewMode === 'cards'}
              className={`px-3 py-2 flex items-center gap-2 text-sm transition border-l border-gray-300 dark:border-gray-600 ${
                viewMode === 'cards'
                  ? 'bg-primary-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
            >
              <LayoutGrid size={16} />
              Cards
            </button>
          </div>
          <button
            onClick={() => navigate('/editor')}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2"
          >
            <FileCode size={16} />
            New Pipeline
          </button>
        </div>
      </div>

      {viewMode === 'cards' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {pipelines?.map((pipeline) => (
            <PipelineCard
              key={pipeline.id}
              pipeline={pipeline}
              onExecute={() => handleExecute(pipeline)}
              onEdit={() => navigate(`/editor/${pipeline.id}`)}
              isExecuting={executeMutation.isPending}
            />
          ))}
        </div>
      ) : (
        <PipelineTable
          pipelines={pipelines}
          onExecute={handleExecute}
          onEdit={(pipeline) => navigate(`/editor/${pipeline.id}`)}
          isExecuting={executeMutation.isPending}
        />
      )}

      {/* Execution Dialog */}
      {executionDialog && (
        <div className="fixed inset-0 bg-black/50 dark:bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full my-8 flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
              <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">
                Execute: {executionDialog.name}
              </h2>
              <button
                onClick={() => setExecutionDialog(null)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
              >
                <X size={24} />
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1">
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Input Data
                </label>
                <div className="inline-flex rounded-lg border border-gray-300 dark:border-gray-600 overflow-hidden text-xs">
                  <button
                    type="button"
                    onClick={() => switchInputMode('form')}
                    aria-pressed={inputMode === 'form'}
                    className={`px-3 py-1.5 transition ${
                      inputMode === 'form'
                        ? 'bg-primary-600 text-white'
                        : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                    }`}
                  >
                    Form
                  </button>
                  <button
                    type="button"
                    onClick={() => switchInputMode('json')}
                    aria-pressed={inputMode === 'json'}
                    className={`px-3 py-1.5 transition border-l border-gray-300 dark:border-gray-600 ${
                      inputMode === 'json'
                        ? 'bg-primary-600 text-white'
                        : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                    }`}
                  >
                    JSON
                  </button>
                </div>
              </div>

              {inputMode === 'form' ? (
                <ParameterForm
                  parameters={executionDialog.config?.parameters || []}
                  values={formValues}
                  onChange={handleFormFieldChange}
                />
              ) : (
                <>
                  <textarea
                    value={inputData}
                    onChange={(e) => setInputData(e.target.value)}
                    className="w-full h-64 p-3 border border-gray-300 dark:border-gray-600 rounded-lg font-mono text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                    placeholder="{}"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    Edit the JSON input data for this pipeline execution
                  </p>
                </>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 flex-shrink-0">
              <button
                onClick={() => setExecutionDialog(null)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmExecution}
                disabled={executeMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2 transition"
              >
                {executeMutation.isPending ? (
                  <>
                    <ButtonSpinner />
                    Executing...
                  </>
                ) : (
                  <>
                    <Play size={16} />
                    Execute Pipeline
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function PipelineTable({ pipelines, onExecute, onEdit, isExecuting }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900/50 text-left text-gray-600 dark:text-gray-300">
            <tr>
              <th className="px-4 py-3 font-semibold">Name</th>
              <th className="px-4 py-3 font-semibold">Description</th>
              <th className="px-4 py-3 font-semibold">Tags</th>
              <th className="px-4 py-3 font-semibold">Created</th>
              <th className="px-4 py-3 font-semibold text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {pipelines?.map((pipeline) => (
              <tr key={pipeline.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="bg-primary-100 dark:bg-primary-900/30 rounded p-1.5">
                      <FileCode className="text-primary-600 dark:text-primary-400" size={16} />
                    </div>
                    <span className="font-semibold text-gray-800 dark:text-gray-100">{pipeline.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-md">
                  <p className="line-clamp-2">{pipeline.description}</p>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {pipeline.tags.map((tag) => (
                      <span key={tag} className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-0.5 rounded text-xs">
                        {tag}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                  {new Date(pipeline.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => onEdit(pipeline)}
                      className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition flex items-center gap-1.5"
                    >
                      <Edit size={14} />
                      Edit
                    </button>
                    <button
                      onClick={() => onExecute(pipeline)}
                      disabled={isExecuting}
                      className="px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition flex items-center gap-1.5"
                    >
                      {isExecuting ? (
                        <>
                          <ButtonSpinner />
                          Executing...
                        </>
                      ) : (
                        <>
                          <Play size={14} />
                          Execute
                        </>
                      )}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function PipelineCard({ pipeline, onExecute, onEdit, isExecuting }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-lg dark:hover:shadow-2xl transition p-6 border border-gray-200 dark:border-gray-700">
      <div className="flex items-start justify-between mb-4">
        <div className="bg-primary-100 dark:bg-primary-900/30 rounded-lg p-3">
          <FileCode className="text-primary-600 dark:text-primary-400" size={24} />
        </div>
      </div>

      <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-2">{pipeline.name}</h3>
      <p className="text-gray-600 dark:text-gray-400 text-sm mb-4 line-clamp-2">{pipeline.description}</p>

      <div className="space-y-2 mb-4">
        <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
          <Tag size={16} className="mr-2" />
          <div className="flex flex-wrap gap-1">
            {pipeline.tags.map((tag) => (
              <span key={tag} className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-xs">
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
          <Calendar size={16} className="mr-2" />
          Created {new Date(pipeline.created_at).toLocaleDateString()}
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <button
          onClick={onEdit}
          className="px-3 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg font-semibold hover:bg-gray-50 dark:hover:bg-gray-700 transition flex items-center gap-2"
        >
          <Edit size={16} />
          Edit
        </button>
        <button
          onClick={onExecute}
          disabled={isExecuting}
          className="flex-1 bg-primary-600 text-white px-4 py-2 rounded-lg font-semibold hover:bg-primary-700 transition disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {isExecuting ? (
            <>
              <ButtonSpinner />
              Executing...
            </>
          ) : (
            <>
              <Play size={16} />
              Execute
            </>
          )}
        </button>
      </div>
    </div>
  )
}

// Renders one input per declared pipeline parameter. Falls back to a JSON
// textarea for complex types (array/object) since form fields don't help there.
function ParameterForm({ parameters, values, onChange }) {
  if (!parameters || parameters.length === 0) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400 italic p-4 bg-gray-50 dark:bg-gray-900/30 rounded-lg border border-gray-200 dark:border-gray-700">
        This pipeline has no declared parameters. Switch to JSON mode if you need to pass raw input.
      </div>
    )
  }
  return (
    <div className="space-y-4">
      {parameters.map((p) => (
        <ParameterField
          key={p.name}
          parameter={p}
          value={values[p.name]}
          onChange={(v) => onChange(p.name, v)}
        />
      ))}
    </div>
  )
}

function ParameterField({ parameter, value, onChange }) {
  const { name, description, required, schema } = parameter
  const type = schema?.type || 'string'
  const label = (
    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
      {name}
      {required && <span className="text-red-500 ml-1">*</span>}
      <span className="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">({type})</span>
    </label>
  )
  const help = description && (
    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{description}</p>
  )
  const inputClass =
    'w-full p-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100'

  if (type === 'boolean') {
    return (
      <div>
        {label}
        <input
          type="checkbox"
          checked={!!value}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4"
        />
        {help}
      </div>
    )
  }

  if (type === 'number' || type === 'integer') {
    return (
      <div>
        {label}
        <input
          type="number"
          value={value ?? ''}
          step={type === 'integer' ? 1 : 'any'}
          onChange={(e) => {
            const raw = e.target.value
            if (raw === '') {
              onChange('')
              return
            }
            const n = type === 'integer' ? parseInt(raw, 10) : parseFloat(raw)
            onChange(Number.isNaN(n) ? raw : n)
          }}
          className={inputClass}
        />
        {help}
      </div>
    )
  }

  if (type === 'array' || type === 'object') {
    const display =
      typeof value === 'string' ? value : JSON.stringify(value ?? (type === 'array' ? [] : {}), null, 2)
    return (
      <div>
        {label}
        <textarea
          value={display}
          onChange={(e) => {
            const raw = e.target.value
            try {
              onChange(JSON.parse(raw))
            } catch {
              // Keep the raw string so the user can keep typing invalid JSON;
              // handleConfirmExecution will surface the parse error on submit.
              onChange(raw)
            }
          }}
          rows={type === 'array' ? 6 : 5}
          className={`${inputClass} font-mono`}
        />
        {help}
      </div>
    )
  }

  // Default: string. Use a textarea for long content, input for short.
  const isLong = typeof value === 'string' && value.length > 80
  return (
    <div>
      {label}
      {isLong ? (
        <textarea
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          className={inputClass}
        />
      ) : (
        <input
          type="text"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
        />
      )}
      {help}
    </div>
  )
}
