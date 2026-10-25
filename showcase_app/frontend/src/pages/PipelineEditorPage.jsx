import { useState, useEffect } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Code, Eye, Columns, Save, Play, ArrowLeft, FolderOpen, X, ChevronDown, ChevronUp } from 'lucide-react';
import VisualCanvas from '../components/editor/VisualCanvas';
import CodeEditor from '../components/editor/CodeEditor';
import ExecutionDetailsModal from '../components/execution/ExecutionDetailsModal';
import { pipelinesAPI, executionAPI, hitlAPI } from '../services/api';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import HITLInteractionModal from '../components/hitl/HITLInteractionModal';
import { useToast } from '../hooks/useToast';


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
    task: 'Analyze customer feedback data',
    text: 'The product quality is excellent but shipping was delayed. Customer service was responsive and helpful.',
  },
  'Human-in-the-Loop Test Pipeline': {},
};

const VIEW_MODES = {
  VISUAL: 'visual',
  CODE: 'code',
  SPLIT: 'split',
};

const INPUT_MODES = {
  FORM: 'form',
  JSON: 'json',
};

export default function PipelineEditorPage() {
  const navigate = useNavigate();
  const { pipelineId } = useParams();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState(VIEW_MODES.VISUAL);
  const [pipelineConfig, setPipelineConfig] = useState(getDefaultPipeline());
  const [codeValue, setCodeValue] = useState(JSON.stringify(pipelineConfig, null, 2));
  const [hasChanges, setHasChanges] = useState(false);
  const [showLoadDialog, setShowLoadDialog] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [showExecutionDialog, setShowExecutionDialog] = useState(false);
  const [inputData, setInputData] = useState('');
  const [executionParamSchema, setExecutionParamSchema] = useState([]);
  const [inputMode, setInputMode] = useState(INPUT_MODES.FORM);
  const [formValues, setFormValues] = useState({});
  const [jsonError, setJsonError] = useState('');
  const [showExecutionsTable, setShowExecutionsTable] = useState(true);
  const [selectedExecution, setSelectedExecution] = useState(null);
  const [selectedHITLInteraction, setSelectedHITLInteraction] = useState(null);
  const toast = useToast();

  const { data: executions = [] } = useQuery({
    queryKey: ['executions', pipelineId],
    queryFn: async () => {
      if (!pipelineId) return [];
      const response = await executionAPI.list();
      return response.data.filter(e => e.pipeline_id === pipelineId);
    },
    enabled: !!pipelineId,
  });

  // Only poll when there's an actively running/waiting execution
  const hasActiveExecution = executions.some(e => e.status === 'running' || e.status === 'waiting_for_human');

  // Fetch pending HITL interactions for this pipeline
  const { data: hitlInteractions = [] } = useQuery({
    queryKey: ['hitl-interactions', pipelineId],
    queryFn: async () => {
      if (!pipelineId) return [];
      const response = await hitlAPI.getPending(null, pipelineId);
      return response.data;
    },
    enabled: !!pipelineId && hasActiveExecution,
    refetchInterval: hasActiveExecution ? 5000 : false,
  });

  // Load existing pipeline if pipelineId is provided
  const { data: existingPipeline, isLoading: isLoadingPipeline } = useQuery({
    queryKey: ['pipeline', pipelineId],
    queryFn: async () => {
      if (!pipelineId) return null;
      const response = await pipelinesAPI.get(pipelineId);
      return response.data;
    },
    enabled: !!pipelineId,
  });

  // Load all pipelines for the selector
  const { data: allPipelines } = useQuery({
    queryKey: ['pipelines'],
    queryFn: async () => {
      const response = await pipelinesAPI.list();
      return response.data;
    },
  });

  // Initialize from existing pipeline or URL params
  useEffect(() => {
    if (existingPipeline) {
      setPipelineConfig(existingPipeline.config);
      setCodeValue(JSON.stringify(existingPipeline.config, null, 2));
      setHasChanges(false);
    } else if (!pipelineId) {
      // Check if pipeline data is passed via URL params
      const pipelineData = searchParams.get('data');
      if (pipelineData) {
        try {
          const config = JSON.parse(decodeURIComponent(pipelineData));
          setPipelineConfig(config);
          setCodeValue(JSON.stringify(config, null, 2));
          setHasChanges(false);
        } catch (e) {
          console.error('Failed to parse pipeline data from URL:', e);
        }
      }
    }
  }, [existingPipeline, pipelineId, searchParams]);

  useEffect(() => {
    // Sync code value when pipeline config changes from visual editor
    setCodeValue(JSON.stringify(pipelineConfig, null, 2));
  }, [pipelineConfig]);

  // WebSocket listener for execution updates
  useEffect(() => {
    if (!pipelineId) return;

    const ws = new WebSocket(`${import.meta.env.VITE_WS_URL || `ws://${window.location.host}`}/ws/pipeline/${pipelineId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // Invalidate executions query to refetch data
      if (data.type === 'execution_completed' || data.type === 'execution_failed' || data.type === 'execution_paused') {
        queryClient.invalidateQueries(['executions', pipelineId]);
        queryClient.invalidateQueries(['hitl-interactions', pipelineId]);
      }
    };

    return () => ws.close();
  }, [pipelineId, queryClient]);

  const handleVisualChange = (newConfig) => {
    setPipelineConfig(newConfig);
    setHasChanges(true);
  };

  const handleCodeChange = (newCode) => {
    setCodeValue(newCode);
    setHasChanges(true);

    // Try to parse and update pipeline config
    try {
      const parsed = JSON.parse(newCode);
      setPipelineConfig(parsed);
    } catch (e) {
      // Invalid JSON, don't update visual view
      console.log('Invalid JSON, keeping visual view unchanged');
    }
  };

  const handleLoadPipeline = (pipeline) => {
    const config = pipeline.config || pipeline;
    setPipelineConfig(config);
    setCodeValue(JSON.stringify(config, null, 2));
    setHasChanges(false);
    setShowLoadDialog(false);
    // Update URL to reflect loaded pipeline
    navigate(`/editor/${pipeline.id}`, { replace: true });
  };

  const handleSave = async () => {
    try {
      // Validate JSON
      const config = JSON.parse(codeValue);

      let response;
      if (pipelineId) {
        // Update existing pipeline
        response = await pipelinesAPI.update(pipelineId, {
          name: config.name,
          description: config.description || '',
          config: config,
          tags: config.tags || []
        });
      } else {
        // Create new pipeline
        response = await pipelinesAPI.create({
          name: config.name || 'Untitled Pipeline',
          description: config.description || '',
          config: config,
          tags: config.tags || []
        });
      }

      if (response.status === 200 || response.status === 201) {
        const result = response.data;
        toast.success('Pipeline saved successfully!');
        setHasChanges(false);
        // Update URL if this was a new pipeline
        if (!pipelineId) {
          navigate(`/editor/${result.id}`, { replace: true });
        }
      } else {
        throw new Error('Failed to save pipeline');
      }
    } catch (error) {
      toast.error(`Error saving pipeline: ${error.message}`);
    }
  };

  const handleRun = () => {
    // pipelineConfig state is always in sync with codeValue via the effect at the top
    const config = pipelineConfig;
    const pipelineName = config.name || existingPipeline?.name || 'Pipeline';
    const defaultInput = DEFAULT_INPUTS[pipelineName] || {};
    const paramSchema = Array.isArray(config.parameters) ? config.parameters : [];

    // Seed form values from the declared parameters, falling back to DEFAULT_INPUTS
    const seededForm = {};
    paramSchema.forEach((p) => {
      seededForm[p.name] = defaultInput[p.name] ?? '';
    });
    // Also include any DEFAULT_INPUTS keys that aren't in the schema (backwards compat)
    Object.keys(defaultInput).forEach((k) => {
      if (!(k in seededForm)) seededForm[k] = defaultInput[k];
    });

    setExecutionParamSchema(paramSchema);
    setFormValues(seededForm);
    setInputData(JSON.stringify(defaultInput, null, 2));
    setInputMode(paramSchema.length > 0 ? INPUT_MODES.FORM : INPUT_MODES.JSON);
    setJsonError('');
    setShowExecutionDialog(true);
  };

  const handleInputDataChange = (value) => {
    setInputData(value);
    if (!value.trim()) {
      setJsonError('');
      return;
    }
    try {
      JSON.parse(value);
      setJsonError('');
    } catch (e) {
      setJsonError(e.message);
    }
  };

  const buildExecutionPayload = (mode = inputMode) => {
    if (mode === INPUT_MODES.FORM) {
      // Coerce form values by declared schema type
      const payload = {};
      executionParamSchema.forEach((p) => {
        const raw = formValues[p.name];
        if (raw === '' || raw === undefined || raw === null) return;
        const type = p.schema?.type;
        if (type === 'number' || type === 'integer') {
          const n = Number(raw);
          if (!Number.isNaN(n)) payload[p.name] = n;
        } else if (type === 'boolean') {
          payload[p.name] = raw === true || raw === 'true';
        } else if (type === 'object' || type === 'array') {
          payload[p.name] = typeof raw === 'string' ? JSON.parse(raw) : raw;
        } else {
          payload[p.name] = raw;
        }
      });
      return payload;
    }
    return JSON.parse(inputData);
  };

  const handleConfirmExecution = async () => {
    try {
      const parsedInput = buildExecutionPayload();
      setIsExecuting(true);
      setExecutionResult(null);
      setShowExecutionDialog(false);

      const response = await executionAPI.start(pipelineId, parsedInput);
      setExecutionResult(response.data);

      // Invalidate executions query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['executions', pipelineId] });
    } catch (error) {
      toast.error(`Error executing pipeline: ${error.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleHITLResponse = async (interactionId, humanInput) => {
    await hitlAPI.respond(interactionId, humanInput);
    // Invalidate queries to refresh data
    queryClient.invalidateQueries({ queryKey: ['hitl-interactions', pipelineId] });
    queryClient.invalidateQueries({ queryKey: ['executions', pipelineId] });
  };

  const handleHITLCancel = async (interactionId) => {
    await hitlAPI.cancel(interactionId);
    queryClient.invalidateQueries({ queryKey: ['hitl-interactions', pipelineId] });
    queryClient.invalidateQueries({ queryKey: ['executions', pipelineId] });
  };

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/pipelines')}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-700 dark:text-gray-300" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {existingPipeline ? existingPipeline.name : 'Pipeline Editor'}
            </h1>
            {existingPipeline && (
              <p className="text-sm text-gray-600 dark:text-gray-400">{existingPipeline.description}</p>
            )}
          </div>
          {hasChanges && <span className="text-sm text-orange-500">● Unsaved changes</span>}
        </div>

        <div className="flex items-center gap-3">
          {/* Load Pipeline Button */}
          <button
            onClick={() => setShowLoadDialog(true)}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 flex items-center gap-2 transition-colors"
          >
            <FolderOpen className="w-4 h-4" />
            Load
          </button>
          {/* View Mode Selector */}
          <div className="flex bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            <button
              onClick={() => setViewMode(VIEW_MODES.VISUAL)}
              className={`px-3 py-2 rounded flex items-center gap-2 transition-colors ${
                viewMode === VIEW_MODES.VISUAL
                  ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600 dark:text-primary-400'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <Eye className="w-4 h-4" />
              Visual
            </button>
            <button
              onClick={() => setViewMode(VIEW_MODES.CODE)}
              className={`px-3 py-2 rounded flex items-center gap-2 transition-colors ${
                viewMode === VIEW_MODES.CODE
                  ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600 dark:text-primary-400'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <Code className="w-4 h-4" />
              Code
            </button>
            <button
              onClick={() => setViewMode(VIEW_MODES.SPLIT)}
              className={`px-3 py-2 rounded flex items-center gap-2 transition-colors ${
                viewMode === VIEW_MODES.SPLIT
                  ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600 dark:text-primary-400'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <Columns className="w-4 h-4" />
              Split
            </button>
          </div>

          {/* Actions */}
          <button
            onClick={handleSave}
            disabled={!hasChanges}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
          >
            <Save className="w-4 h-4" />
            Save
          </button>
        </div>
      </div>

      {/* Editor Content */}
      <div className="flex-1 overflow-hidden">
        {viewMode === VIEW_MODES.VISUAL && (
          <VisualCanvas
            pipelineConfig={pipelineConfig}
            pipelineId={pipelineId}
            onConfigChange={handleVisualChange}
            onRun={handleRun}
            isExecuting={isExecuting}
          />
        )}

        {viewMode === VIEW_MODES.CODE && (
          <div className="h-full p-4">
            <CodeEditor value={codeValue} onChange={handleCodeChange} language="json" />
          </div>
        )}

        {viewMode === VIEW_MODES.SPLIT && (
          <div className="h-full flex">
            <div className="w-1/2 border-r border-gray-200 dark:border-gray-800">
              <VisualCanvas
                pipelineConfig={pipelineConfig}
                pipelineId={pipelineId}
                onConfigChange={handleVisualChange}
                onRun={handleRun}
                isExecuting={isExecuting}
              />
            </div>
            <div className="w-1/2 p-4">
              <CodeEditor value={codeValue} onChange={handleCodeChange} language="json" />
            </div>
          </div>
        )}
      </div>

      {/* Execution Results Panel */}
      {pipelineId && executions && executions.length > 0 && (
        <div className="border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50">
          <button
            onClick={() => setShowExecutionsTable(!showExecutionsTable)}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition"
          >
            <h3 className="font-semibold text-gray-900 dark:text-white">Recent Executions ({executions.length})</h3>
            {showExecutionsTable ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
          {showExecutionsTable && (
            <div className="px-4 pb-4 max-h-96 overflow-y-auto">
              <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded overflow-hidden">
            <table className="min-w-full">
              <thead className="bg-gray-50 dark:bg-gray-800/50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Job ID</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Started</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Duration</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                {executions.map((execution) => {
                  const executionHITL = hitlInteractions.filter(h => h.execution_id === execution.job_id);
                  const hasPendingApproval = executionHITL.length > 0 && execution.status === 'waiting_for_human';

                  return (
                  <tr key={execution.job_id} className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 ${hasPendingApproval ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''}`}>
                    <td className="px-4 py-2 text-xs font-mono text-gray-900 dark:text-gray-200">
                      {execution.job_id.slice(0, 8)}...
                    </td>
                    <td className="px-4 py-2 text-xs">
                      <span className={`px-2 py-1 rounded text-xs ${
                        execution.status === 'completed' ? 'bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300' :
                        execution.status === 'failed' ? 'bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300' :
                        execution.status === 'waiting_for_human' ? 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-800 dark:text-yellow-300' :
                        'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300'
                      }`}>
                        {execution.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600 dark:text-gray-400">
                      {new Date(execution.started_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600 dark:text-gray-400">
                      {execution.execution_time_ms ? `${(execution.execution_time_ms / 1000).toFixed(2)}s` : '-'}
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={async () => {
                          const response = await executionAPI.get(execution.job_id);
                          const exec = response.data;

                          // If waiting for human, get or construct HITL interaction
                          let hitl = executionHITL[0];
                          if (!hitl && exec.status === 'waiting_for_human' && exec.output_data?.status === 'human_input_required') {
                            // Fetch HITL interaction by execution ID
                            try {
                              const hitlResponse = await hitlAPI.getPending(exec.job_id);
                              hitl = hitlResponse.data[0];
                            } catch (e) {
                              console.error('Failed to fetch HITL interaction:', e);
                            }
                          }

                          setSelectedExecution({
                            execution: exec,
                            hitlInteraction: hitl || null
                          });
                        }}
                        className="text-xs text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
            </div>
          )}
        </div>
      )}

      {/* Execution Dialog */}
      {showExecutionDialog && (
        <div className="fixed inset-0 bg-black/50 dark:bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-2xl w-full my-8 flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-800">
              <div className="min-w-0">
                <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Run</div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white truncate">
                  {pipelineConfig?.name || existingPipeline?.name || 'Pipeline'}
                </h2>
              </div>
              <button
                onClick={() => setShowExecutionDialog(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
              >
                <X size={24} />
              </button>
            </div>

            {/* Mode toggle */}
            {executionParamSchema.length > 0 && (
              <div className="px-6 pt-4">
                <div className="inline-flex bg-gray-100 dark:bg-gray-800 rounded-lg p-1 text-sm">
                  <button
                    onClick={() => {
                      // Sync JSON edits back into form values to avoid losing them
                      try {
                        const parsed = JSON.parse(inputData);
                        if (parsed && typeof parsed === 'object') {
                          setFormValues((prev) => ({ ...prev, ...parsed }));
                        }
                      } catch {
                        // invalid JSON — keep existing form values
                      }
                      setInputMode(INPUT_MODES.FORM);
                    }}
                    className={`px-3 py-1 rounded ${
                      inputMode === INPUT_MODES.FORM
                        ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600 dark:text-primary-400'
                        : 'text-gray-600 dark:text-gray-400'
                    }`}
                  >
                    Form
                  </button>
                  <button
                    onClick={() => {
                      // Sync current form values into the JSON view when switching
                      setInputData(
                        JSON.stringify(buildExecutionPayload(INPUT_MODES.FORM), null, 2)
                      );
                      setJsonError('');
                      setInputMode(INPUT_MODES.JSON);
                    }}
                    className={`px-3 py-1 rounded ${
                      inputMode === INPUT_MODES.JSON
                        ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600 dark:text-primary-400'
                        : 'text-gray-600 dark:text-gray-400'
                    }`}
                  >
                    Raw JSON
                  </button>
                </div>
              </div>
            )}

            <div className="p-6 overflow-y-auto flex-1">
              {inputMode === INPUT_MODES.FORM && executionParamSchema.length > 0 ? (
                <div className="space-y-4">
                  {executionParamSchema.map((param) => {
                    const type = param.schema?.type || 'string';
                    const value = formValues[param.name] ?? '';
                    const isLong = type === 'string' && String(value).length > 80;
                    return (
                      <div key={param.name}>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          {param.name}
                          {param.required && <span className="text-red-500 ml-1">*</span>}
                          <span className="ml-2 text-xs font-normal text-gray-400">{type}</span>
                        </label>
                        {param.description && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                            {param.description}
                          </p>
                        )}
                        {type === 'boolean' ? (
                          <select
                            value={String(value)}
                            onChange={(e) =>
                              setFormValues({ ...formValues, [param.name]: e.target.value === 'true' })
                            }
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                          >
                            <option value="false">false</option>
                            <option value="true">true</option>
                          </select>
                        ) : type === 'object' || type === 'array' ? (
                          <textarea
                            value={typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                            onChange={(e) =>
                              setFormValues({ ...formValues, [param.name]: e.target.value })
                            }
                            rows={6}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-mono text-xs"
                          />
                        ) : isLong ? (
                          <textarea
                            value={value}
                            onChange={(e) =>
                              setFormValues({ ...formValues, [param.name]: e.target.value })
                            }
                            rows={4}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm"
                          />
                        ) : (
                          <input
                            type={type === 'number' || type === 'integer' ? 'number' : 'text'}
                            value={value}
                            onChange={(e) =>
                              setFormValues({ ...formValues, [param.name]: e.target.value })
                            }
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm"
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Input Data (JSON)
                  </label>
                  <textarea
                    value={inputData}
                    onChange={(e) => handleInputDataChange(e.target.value)}
                    className={`w-full h-64 p-3 border rounded-lg font-mono text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ${
                      jsonError
                        ? 'border-red-400 dark:border-red-500 focus:ring-red-500'
                        : 'border-gray-300 dark:border-gray-700'
                    }`}
                    placeholder="{}"
                  />
                  {jsonError ? (
                    <p className="text-xs text-red-500 mt-2">Invalid JSON: {jsonError}</p>
                  ) : (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                      Edit the JSON input data for this pipeline execution
                    </p>
                  )}
                </>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50">
              <button
                onClick={() => setShowExecutionDialog(false)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmExecution}
                disabled={isExecuting || (inputMode === INPUT_MODES.JSON && !!jsonError)}
                className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition"
              >
                <Play size={16} />
                Run
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Load Pipeline Dialog */}
      {showLoadDialog && (
        <div className="fixed inset-0 bg-black/50 dark:bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full my-8 flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">
                Load Pipeline
              </h2>
              <button
                onClick={() => setShowLoadDialog(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
              >
                ×
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1">
              {allPipelines && allPipelines.length > 0 ? (
                <div className="space-y-3">
                  {allPipelines.map((pipeline) => (
                    <div
                      key={pipeline.id}
                      onClick={() => handleLoadPipeline(pipeline)}
                      className="p-4 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition"
                    >
                      <h3 className="font-semibold text-gray-800 dark:text-gray-100">
                        {pipeline.name}
                      </h3>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        {pipeline.description}
                      </p>
                      <div className="flex items-center gap-2 mt-2">
                        {pipeline.tags.map((tag) => (
                          <span
                            key={tag}
                            className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-xs rounded"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-gray-600 dark:text-gray-400">No pipelines available</p>
                  <button
                    onClick={() => navigate('/pipelines')}
                    className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                  >
                    Go to Pipelines Page
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Execution Details Modal */}
      {selectedExecution && (
        <ExecutionDetailsModal
          execution={selectedExecution.execution}
          hitlInteraction={selectedExecution.hitlInteraction}
          onHITLApprove={(interaction) => setSelectedHITLInteraction(interaction)}
          onClose={() => setSelectedExecution(null)}
        />
      )}

      {/* HITL Interaction Modal */}
      {selectedHITLInteraction && (
        <HITLInteractionModal
          interaction={selectedHITLInteraction}
          onRespond={handleHITLResponse}
          onCancel={handleHITLCancel}
          onClose={() => setSelectedHITLInteraction(null)}
        />
      )}
    </div>
  );
}

function getDefaultPipeline() {
  return {
    name: 'New Pipeline',
    description: 'Create your pipeline here',
    steps: [],
    flow: {
      start_at: '',
      paths: [],
    },
  };
}
