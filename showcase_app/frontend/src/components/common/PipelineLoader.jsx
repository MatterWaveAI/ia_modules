import React, { useState, useEffect } from 'react'
import { pipelinesAPI } from '../../services/api'
import { FileText, Eye, Code, Import, Calendar, Tag } from 'lucide-react'

export default function PipelineLoader({ onImportPipeline }) {
  const [pipelines, setPipelines] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedPipeline, setSelectedPipeline] = useState(null)
  const [viewMode, setViewMode] = useState('details') // 'details' or 'json'

  useEffect(() => {
    loadPipelines()
  }, [])

  const loadPipelines = async () => {
    try {
      setLoading(true)
      const response = await pipelinesAPI.list()
      setPipelines(response.data || [])
    } catch (error) {
      console.error('Failed to load pipelines:', error)
      setPipelines([])
    } finally {
      setLoading(false)
    }
  }

  const handleImportPipeline = (pipeline) => {
    if (onImportPipeline) {
      // Convert pipeline config to drag-drop items
      const items = convertPipelineToItems(pipeline)
      onImportPipeline(items, pipeline.name)
    }
  }

  const convertPipelineToItems = (pipeline) => {
    const config = pipeline.config || {}
    const steps = config.steps || []

    // Convert steps to draggable items
    const stepItems = steps.map((step, index) => ({
      id: step.id || `step-${index}`,
      component: getComponentTypeFromStep(step),
      visible: true,
      props: {
        step: {
          name: step.name,
          config: step.config || {}
        }
      }
    }))

    // Add default UI components
    const defaultItems = [
      { id: 'execution-header', component: 'ExecutionHeader', visible: true, props: { onBack: () => {} } },
      { id: 'execution-status', component: 'ExecutionStatusCard', visible: true, props: {} },
      { id: 'execution-timeline', component: 'ExecutionTimeline', visible: true, props: {} },
      { id: 'pipeline-graph', component: 'PipelineGraphSection', visible: true, props: {} },
      { id: 'step-details', component: 'StepDetailsList', visible: true, props: {} },
    ]

    return [...defaultItems, ...stepItems]
  }

  const getComponentTypeFromStep = (step) => {
    const stepClass = step.step_class || ''
    const name = step.name || ''

    // Map step classes to component types
    const classMapping = {
      'WebScrapingStep': 'WebScrapingStep',
      'ContentAnalysisStep': 'ContentAnalysisStep',
      'ReportGenerationStep': 'ReportGenerationStep',
      'PlanningStep': 'PlanningStep',
      'ToolUseStep': 'ToolUseStep',
      'ReflectionStep': 'ReflectionStep',
    }

    // Also check by name patterns
    const nameMapping = {
      'agent': 'AgentStep',
      'llm': 'LLMCallStep',
      'guardrail': 'GuardrailsStep',
      'tool': 'ToolUseStep',
    }

    return classMapping[stepClass] ||
           Object.entries(nameMapping).find(([key, value]) =>
             name.toLowerCase().includes(key)
           )?.[1] ||
           'AgentStep' // Default fallback
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown'
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (loading) {
    return (
      <div className="p-4 text-center">
        <div className="text-gray-600 dark:text-gray-400">Loading saved pipelines...</div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-md border border-gray-200 dark:border-gray-700">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 flex items-center">
          <FileText className="w-5 h-5 mr-2" />
          Saved Pipelines
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">View and import your saved pipeline configurations</p>
      </div>

      <div className="p-4 max-h-96 overflow-y-auto">
        {pipelines.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <FileText className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No saved pipelines found</p>
            <p className="text-sm">Create and save pipelines using the drag-and-drop builder</p>
          </div>
        ) : (
          <div className="space-y-3">
            {pipelines.map((pipeline) => (
              <div
                key={pipeline.id || pipeline.name}
                className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-800 dark:text-gray-100">{pipeline.name}</h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{pipeline.description}</p>

                    <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                      <span className="flex items-center">
                        <Calendar className="w-3 h-3 mr-1" />
                        {formatDate(pipeline.created_at)}
                      </span>
                      {pipeline.metadata?.author && (
                        <span>by {pipeline.metadata.author}</span>
                      )}
                      {pipeline.metadata?.tags && pipeline.metadata.tags.length > 0 && (
                        <div className="flex items-center space-x-1">
                          <Tag className="w-3 h-3" />
                          <div className="flex space-x-1">
                            {pipeline.metadata.tags.slice(0, 2).map((tag, index) => (
                              <span key={index} className="bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                                {tag}
                              </span>
                            ))}
                            {pipeline.metadata.tags.length > 2 && (
                              <span className="text-gray-400">+{pipeline.metadata.tags.length - 2}</span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {pipeline.config?.steps && (
                      <div className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                        {pipeline.config.steps.length} step{pipeline.config.steps.length !== 1 ? 's' : ''}
                      </div>
                    )}
                  </div>

                  <div className="flex space-x-2 ml-4">
                    <button
                      onClick={() => setSelectedPipeline(pipeline)}
                      className="flex items-center px-3 py-1 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded text-sm transition-colors"
                      title="View pipeline details"
                    >
                      <Eye className="w-4 h-4 mr-1" />
                      View
                    </button>
                    <button
                      onClick={() => handleImportPipeline(pipeline)}
                      className="flex items-center px-3 py-1 bg-blue-600 text-white hover:bg-blue-700 rounded text-sm transition-colors"
                      title="Import into drag-and-drop builder"
                    >
                      <Import className="w-4 h-4 mr-1" />
                      Import
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pipeline Details Modal */}
      {selectedPipeline && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-900 rounded-lg max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-xl font-semibold text-gray-800 dark:text-gray-100">
                Pipeline: {selectedPipeline.name}
              </h3>
              <div className="flex space-x-2">
                <button
                  onClick={() => setViewMode(viewMode === 'details' ? 'json' : 'details')}
                  className="flex items-center px-3 py-1 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded text-sm transition-colors"
                  title={viewMode === 'details' ? 'View JSON' : 'View Details'}
                >
                  <Code className="w-4 h-4 mr-1" />
                  {viewMode === 'details' ? 'JSON' : 'Details'}
                </button>
                <button
                  onClick={() => setSelectedPipeline(null)}
                  className="px-3 py-1 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                >
                  ✕
                </button>
              </div>
            </div>

            <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
              {viewMode === 'details' ? (
                <div className="space-y-6">
                  {/* Basic Info */}
                  <div>
                    <h4 className="font-semibold text-gray-800 dark:text-gray-100 mb-2">Basic Information</h4>
                    <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-4 space-y-2">
                      <div><strong>Name:</strong> {selectedPipeline.name}</div>
                      <div><strong>Description:</strong> {selectedPipeline.description}</div>
                      <div><strong>Version:</strong> {selectedPipeline.version}</div>
                      {selectedPipeline.created_at && (
                        <div><strong>Created:</strong> {formatDate(selectedPipeline.created_at)}</div>
                      )}
                      {selectedPipeline.metadata?.author && (
                        <div><strong>Author:</strong> {selectedPipeline.metadata.author}</div>
                      )}
                    </div>
                  </div>

                  {/* Steps */}
                  {selectedPipeline.config?.steps && (
                    <div>
                      <h4 className="font-semibold text-gray-800 dark:text-gray-100 mb-2">Pipeline Steps</h4>
                      <div className="space-y-2">
                        {selectedPipeline.config.steps.map((step, index) => (
                          <div key={step.id || index} className="bg-gray-50 dark:bg-gray-800/50 rounded p-3">
                            <div className="flex items-center justify-between">
                              <div>
                                <span className="font-medium">{step.name}</span>
                                <span className="text-sm text-gray-600 dark:text-gray-400 ml-2">({step.step_class})</span>
                              </div>
                              <span className="text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 px-2 py-1 rounded">
                                Step {index + 1}
                              </span>
                            </div>
                            {step.config && Object.keys(step.config).length > 0 && (
                              <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                <strong>Config:</strong> {JSON.stringify(step.config)}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Flow */}
                  {selectedPipeline.config?.flow && (
                    <div>
                      <h4 className="font-semibold text-gray-800 dark:text-gray-100 mb-2">Flow Configuration</h4>
                      <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-4">
                        <div><strong>Start At:</strong> {selectedPipeline.config.flow.start_at}</div>
                        <div className="mt-2">
                          <strong>Paths:</strong>
                          <ul className="list-disc list-inside mt-1 space-y-1">
                            {selectedPipeline.config.flow.paths?.map((path, index) => (
                              <li key={index}>
                                {path.from} → {path.to} ({path.condition?.type || 'unknown'})
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Metadata */}
                  {selectedPipeline.metadata && (
                    <div>
                      <h4 className="font-semibold text-gray-800 dark:text-gray-100 mb-2">Metadata</h4>
                      <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-4">
                        {selectedPipeline.metadata.tags && (
                          <div className="mb-2">
                            <strong>Tags:</strong>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {selectedPipeline.metadata.tags.map((tag, index) => (
                                <span key={index} className="bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 px-2 py-1 rounded text-sm">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        <div><strong>Category:</strong> {selectedPipeline.metadata.category || 'Uncategorized'}</div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <h4 className="font-semibold text-gray-800 dark:text-gray-100 mb-4">Pipeline JSON Configuration</h4>
                  <pre className="bg-gray-900 text-green-400 p-4 rounded text-sm overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(selectedPipeline, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <div className="flex justify-end space-x-3 p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <button
                onClick={() => setSelectedPipeline(null)}
                className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              >
                Close
              </button>
              <button
                onClick={() => {
                  handleImportPipeline(selectedPipeline)
                  setSelectedPipeline(null)
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Import to Builder
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}