import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { pluginsAPI } from '../services/api'
import { Puzzle, Play, Tag, ChevronRight, X, Upload, Trash2, CheckCircle, XCircle, Info, Loader2 } from 'lucide-react'
import { LoadingSpinner, ButtonSpinner } from '../components/ui/spinner'
import { SkeletonCard } from '../components/ui/skeleton'
import { EmptyState } from '../components/ui/empty-state'
import { useToast } from '../hooks/useToast'

// Plugin type color mapping
const TYPE_COLORS = {
  condition: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-300', border: 'border-blue-200 dark:border-blue-800' },
  step: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-300', border: 'border-green-200 dark:border-green-800' },
  validator: { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-700 dark:text-purple-300', border: 'border-purple-200 dark:border-purple-800' },
  transform: { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-700 dark:text-orange-300', border: 'border-orange-200 dark:border-orange-800' },
  hook: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', text: 'text-yellow-700 dark:text-yellow-300', border: 'border-yellow-200 dark:border-yellow-800' },
  reporter: { bg: 'bg-pink-100 dark:bg-pink-900/30', text: 'text-pink-700 dark:text-pink-300', border: 'border-pink-200 dark:border-pink-800' },
}

// Example input data for builtin plugins
const EXAMPLE_PARAMS = {
  business_hours: { current_time: '2026-04-04T14:30:00' },
  time_range: { current_time: '2026-04-04T14:30:00' },
  day_of_week: { current_time: '2026-04-04T14:30:00' },
  email_validator: { email: 'user@example.com' },
  range_validator: { value: 42 },
  regex_validator: { field_value: 'test-123' },
  schema_validator: { name: 'Test', email: 'test@example.com' },
  weather_condition: { weather: { condition: 'sunny', temperature: 22, humidity: 45 } },
  is_good_weather: { weather: { condition: 'sunny', temperature: 22, humidity: 45 } },
  api_status_condition: { api_response: { status_code: 200, data: {} } },
  api_data_condition: { api_response: { status_code: 200, data: { status: 'ok' } } },
  api_call_step: {},
  database_record_exists: { id: 1, _db_records: { users: { 1: { name: 'Test' } } } },
  database_value_condition: { score: 85 },
}

export default function PluginsPage() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [selectedPlugin, setSelectedPlugin] = useState(null)
  const [executeParams, setExecuteParams] = useState('{}')
  const [executeResult, setExecuteResult] = useState(null)
  const [loadDialogOpen, setLoadDialogOpen] = useState(false)
  const [loadPath, setLoadPath] = useState('')
  const [filterType, setFilterType] = useState('all')

  const { data: plugins, isLoading, error } = useQuery({
    queryKey: ['plugins'],
    queryFn: async () => {
      const response = await pluginsAPI.list()
      return response.data
    },
  })

  const { data: pluginDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['plugin', selectedPlugin],
    queryFn: async () => {
      const response = await pluginsAPI.get(selectedPlugin)
      return response.data
    },
    enabled: !!selectedPlugin,
  })

  const executeMutation = useMutation({
    mutationFn: async ({ name, params }) => {
      const response = await pluginsAPI.execute(name, params)
      return response.data
    },
    onSuccess: (data) => {
      setExecuteResult(data)
      toast.success(`Plugin "${data.plugin}" executed successfully`)
    },
    onError: (error) => {
      toast.error(`Execution failed: ${error.response?.data?.detail || error.message}`)
    },
  })

  const loadMutation = useMutation({
    mutationFn: async (path) => {
      const response = await pluginsAPI.load(path)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries(['plugins'])
      setLoadDialogOpen(false)
      setLoadPath('')
      toast.success(data.message)
    },
    onError: (error) => {
      toast.error(`Load failed: ${error.response?.data?.detail || error.message}`)
    },
  })

  const unloadMutation = useMutation({
    mutationFn: async (name) => {
      const response = await pluginsAPI.unload(name)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries(['plugins'])
      setSelectedPlugin(null)
      setExecuteResult(null)
      toast.success(data.message)
    },
    onError: (error) => {
      toast.error(`Unload failed: ${error.response?.data?.detail || error.message}`)
    },
  })

  const handleSelectPlugin = (name) => {
    setSelectedPlugin(name)
    setExecuteResult(null)
    const example = EXAMPLE_PARAMS[name] || {}
    setExecuteParams(JSON.stringify(example, null, 2))
  }

  const handleExecute = () => {
    try {
      const params = JSON.parse(executeParams)
      executeMutation.mutate({ name: selectedPlugin, params })
    } catch (e) {
      toast.error(`Invalid JSON: ${e.message}`)
    }
  }

  const filteredPlugins = plugins?.filter(
    (p) => filterType === 'all' || p.type === filterType
  )

  const pluginTypes = plugins ? [...new Set(plugins.map((p) => p.type))] : []

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Plugins</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Manage and execute registered plugins</p>
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
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Plugins</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Manage and execute registered plugins</p>
        </div>
        <EmptyState
          icon={Puzzle}
          title="Failed to load plugins"
          description={error.message || "Could not load plugins. Is the backend running?"}
          action={() => queryClient.invalidateQueries(['plugins'])}
          actionLabel="Retry"
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Plugins</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {plugins?.length || 0} plugin{plugins?.length !== 1 ? 's' : ''} registered
          </p>
        </div>
        <button
          onClick={() => setLoadDialogOpen(true)}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2 transition"
        >
          <Upload size={16} />
          Load Plugin
        </button>
      </div>

      {/* Type Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setFilterType('all')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
            filterType === 'all'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
          }`}
        >
          All ({plugins?.length || 0})
        </button>
        {pluginTypes.map((type) => {
          const colors = TYPE_COLORS[type] || TYPE_COLORS.condition
          const count = plugins?.filter((p) => p.type === type).length || 0
          return (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                filterType === type
                  ? 'bg-primary-600 text-white'
                  : `${colors.bg} ${colors.text} hover:opacity-80`
              }`}
            >
              {type} ({count})
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Plugin List */}
        <div className="lg:col-span-1 space-y-3">
          {filteredPlugins?.map((plugin) => (
            <PluginCard
              key={plugin.name}
              plugin={plugin}
              isSelected={selectedPlugin === plugin.name}
              onClick={() => handleSelectPlugin(plugin.name)}
            />
          ))}
          {filteredPlugins?.length === 0 && (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              No plugins match the selected filter.
            </div>
          )}
        </div>

        {/* Plugin Detail + Execute Panel */}
        <div className="lg:col-span-2 space-y-4">
          {selectedPlugin ? (
            <>
              {/* Detail Panel */}
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-6">
                {detailLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <LoadingSpinner />
                  </div>
                ) : pluginDetail ? (
                  <div className="space-y-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">
                          {pluginDetail.name}
                        </h2>
                        <p className="text-gray-600 dark:text-gray-400 mt-1">
                          {pluginDetail.description || 'No description'}
                        </p>
                      </div>
                      <button
                        onClick={() => unloadMutation.mutate(selectedPlugin)}
                        disabled={unloadMutation.isPending}
                        className="px-3 py-1.5 text-sm border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition flex items-center gap-1"
                      >
                        {unloadMutation.isPending ? <ButtonSpinner /> : <Trash2 size={14} />}
                        Unload
                      </button>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <DetailItem label="Version" value={pluginDetail.version} />
                      <DetailItem label="Type" value={pluginDetail.type} />
                      <DetailItem label="Author" value={pluginDetail.author || 'Unknown'} />
                      <DetailItem
                        label="Status"
                        value={
                          <span className="flex items-center gap-1">
                            <CheckCircle size={14} className="text-green-500" />
                            {pluginDetail.status}
                          </span>
                        }
                      />
                    </div>

                    {pluginDetail.tags?.length > 0 && (
                      <div>
                        <span className="text-sm font-medium text-gray-500 dark:text-gray-400">Tags</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {pluginDetail.tags.map((tag) => (
                            <span
                              key={tag}
                              className="bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded text-xs text-gray-600 dark:text-gray-300"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {pluginDetail.dependencies?.length > 0 && (
                      <div>
                        <span className="text-sm font-medium text-gray-500 dark:text-gray-400">Dependencies</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {pluginDetail.dependencies.map((dep) => (
                            <span
                              key={dep}
                              className={`px-2 py-0.5 rounded text-xs ${
                                pluginDetail.missing_dependencies?.includes(dep)
                                  ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                                  : 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
                              }`}
                            >
                              {dep} {pluginDetail.missing_dependencies?.includes(dep) ? '(missing)' : ''}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}
              </div>

              {/* Execute Panel */}
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-6">
                <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-4 flex items-center gap-2">
                  <Play size={18} className="text-primary-600 dark:text-primary-400" />
                  Execute Plugin
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Parameters (JSON)
                    </label>
                    <textarea
                      value={executeParams}
                      onChange={(e) => setExecuteParams(e.target.value)}
                      className="w-full h-40 p-3 border border-gray-300 dark:border-gray-600 rounded-lg font-mono text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition"
                      placeholder="{}"
                    />
                  </div>

                  <button
                    onClick={handleExecute}
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
                        Execute
                      </>
                    )}
                  </button>

                  {/* Results */}
                  {executeResult && (
                    <div className={`mt-4 p-4 rounded-lg border ${
                      executeResult.success
                        ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                        : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                    }`}>
                      <div className="flex items-center gap-2 mb-2">
                        {executeResult.success ? (
                          <CheckCircle size={16} className="text-green-600 dark:text-green-400" />
                        ) : (
                          <XCircle size={16} className="text-red-600 dark:text-red-400" />
                        )}
                        <span className={`font-medium text-sm ${
                          executeResult.success
                            ? 'text-green-700 dark:text-green-300'
                            : 'text-red-700 dark:text-red-300'
                        }`}>
                          {executeResult.success ? 'Execution Successful' : 'Execution Failed'}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400 ml-auto">
                          Type: {executeResult.type}
                        </span>
                      </div>
                      <pre className="text-sm font-mono whitespace-pre-wrap break-words text-gray-800 dark:text-gray-200 bg-white/50 dark:bg-gray-800/50 p-3 rounded">
                        {JSON.stringify(executeResult.result, null, 2)}
                      </pre>
                      {executeResult.error && (
                        <p className="text-sm text-red-600 dark:text-red-400 mt-2">
                          Error: {executeResult.error}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-12 text-center">
              <Info size={48} className="mx-auto text-gray-300 dark:text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-600 dark:text-gray-400">Select a Plugin</h3>
              <p className="text-sm text-gray-500 dark:text-gray-500 mt-1">
                Click on a plugin card to view details and execute it
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Load Plugin Dialog */}
      {loadDialogOpen && (
        <div className="fixed inset-0 bg-black/50 dark:bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full">
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Load Plugin</h2>
              <button
                onClick={() => setLoadDialogOpen(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
              >
                <X size={24} />
              </button>
            </div>
            <div className="p-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Plugin File Path
              </label>
              <input
                type="text"
                value={loadPath}
                onChange={(e) => setLoadPath(e.target.value)}
                className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition"
                placeholder="/path/to/plugin.py"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                Enter the absolute file path to a Python plugin file
              </p>
            </div>
            <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
              <button
                onClick={() => setLoadDialogOpen(false)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => loadMutation.mutate(loadPath)}
                disabled={!loadPath || loadMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2 transition"
              >
                {loadMutation.isPending ? (
                  <>
                    <ButtonSpinner />
                    Loading...
                  </>
                ) : (
                  <>
                    <Upload size={16} />
                    Load Plugin
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

function PluginCard({ plugin, isSelected, onClick }) {
  const colors = TYPE_COLORS[plugin.type] || TYPE_COLORS.condition

  return (
    <div
      onClick={onClick}
      className={`bg-white dark:bg-gray-800 rounded-lg shadow border p-4 cursor-pointer transition hover:shadow-md ${
        isSelected
          ? 'border-primary-500 dark:border-primary-400 ring-2 ring-primary-500/20'
          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={`${colors.bg} rounded-lg p-2`}>
            <Puzzle size={18} className={colors.text} />
          </div>
          <div>
            <h3 className="font-semibold text-gray-800 dark:text-gray-100 text-sm">{plugin.name}</h3>
            <span className="text-xs text-gray-500 dark:text-gray-400">v{plugin.version}</span>
          </div>
        </div>
        <ChevronRight size={16} className={`text-gray-400 transition ${isSelected ? 'rotate-90' : ''}`} />
      </div>

      <p className="text-gray-600 dark:text-gray-400 text-xs mb-2 line-clamp-2">
        {plugin.description || 'No description'}
      </p>

      <div className="flex items-center justify-between">
        <span className={`text-xs px-2 py-0.5 rounded-full ${colors.bg} ${colors.text}`}>
          {plugin.type}
        </span>
        <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
          <CheckCircle size={12} />
          {plugin.status}
        </span>
      </div>
    </div>
  )
}

function DetailItem({ label, value }) {
  return (
    <div>
      <span className="text-xs font-medium text-gray-500 dark:text-gray-400 block">{label}</span>
      <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{value}</span>
    </div>
  )
}
