import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Brain, Target, Wrench, Search, Activity, Play, Sparkles, Plus, Trash2, ArrowLeft, ChevronDown, ChevronRight, Radio } from 'lucide-react';
import ReflectionViz from '../components/patterns/ReflectionViz';
import PlanningViz from '../components/patterns/PlanningViz';
import AgenticRAGViz from '../components/patterns/AgenticRAGViz';

// Map frontend URL slug -> backend pattern name emitted in ws events.
const PATTERN_EVENT_NAMES = {
  'reflection': 'reflection',
  'planning': 'planning',
  'tool-use': 'tool_use',
  'agentic-rag': 'agentic_rag',
  'metacognition': 'metacognition',
};

const PATTERNS = [
  {
    id: 'reflection',
    name: 'Reflection',
    icon: Brain,
    color: 'purple',
    description: 'Self-critique and iterative improvement',
  },
  {
    id: 'planning',
    name: 'Planning',
    icon: Target,
    color: 'blue',
    description: 'Multi-step goal decomposition',
  },
  {
    id: 'tool-use',
    name: 'Tool Use',
    icon: Wrench,
    color: 'orange',
    description: 'Dynamic tool selection',
  },
  {
    id: 'agentic-rag',
    name: 'Agentic RAG',
    icon: Search,
    color: 'green',
    description: 'Query refinement and retrieval',
  },
  {
    id: 'metacognition',
    name: 'Metacognition',
    icon: Activity,
    color: 'pink',
    description: 'Self-monitoring and adaptation',
  },
];

const COLOR_CLASSES = {
  purple: 'from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700',
  blue: 'from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700',
  orange: 'from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700',
  green: 'from-green-500 to-green-600 hover:from-green-600 hover:to-green-700',
  pink: 'from-pink-500 to-pink-600 hover:from-pink-600 hover:to-pink-700',
};

/**
 * Agentic Patterns Page
 * Demonstrates advanced agentic design patterns with editable configuration
 */
export default function PatternsPage() {
  const { patternId } = useParams();
  const navigate = useNavigate();
  const selectedPattern = patternId || null;
  const [patternData, setPatternData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [events, setEvents] = useState([]);
  const [formCollapsed, setFormCollapsed] = useState(false);
  const [eventsCollapsed, setEventsCollapsed] = useState(false);
  const wsRef = useRef(null);
  const eventsEndRef = useRef(null);

  // Reset state when navigating between patterns
  useEffect(() => {
    setPatternData(null);
    setError(null);
    setEvents([]);
    setFormCollapsed(false);
  }, [patternId]);

  // Tear down any live WebSocket on unmount / pattern change
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        try { wsRef.current.close(); } catch { /* ignore */ }
        wsRef.current = null;
      }
    };
  }, [patternId]);

  // Auto-scroll the live event log as new events arrive
  useEffect(() => {
    if (eventsEndRef.current) {
      eventsEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [events]);

  // Per-pattern editable form state
  const [reflectionConfig, setReflectionConfig] = useState({
    initial_output: 'AI is useful.',
    criteria: {
      clarity: 'Explain clearly and concisely',
      completeness: 'Cover key aspects comprehensively',
      accuracy: 'Provide factual information'
    }
  });

  const [planningConfig, setPlanningConfig] = useState({
    goal: 'Research the impact of AI on education',
    constraints: {
      time: '2 hours',
      depth: 'comprehensive'
    }
  });

  const [toolUseConfig, setToolUseConfig] = useState({
    task: 'Find and analyze recent research papers on quantum computing',
    available_tools: ['web_search', 'database_query', 'llm_analyzer', 'python_executor', 'file_system']
  });

  const [ragConfig, setRagConfig] = useState({
    query: 'machine learning applications',
    max_refinements: 3
  });

  const [metacognitionConfig, setMetacognitionConfig] = useState({
    execution_trace: [
      { step: 'search', status: 'success', duration: 2.3 },
      { step: 'analyze', status: 'success', duration: 1.8 },
      { step: 'generate', status: 'error', duration: 0.5 },
      { step: 'retry_generate', status: 'success', duration: 2.1 }
    ],
    performance_metrics: {
      accuracy: 0.85,
      efficiency: 0.72,
      reliability: 0.90
    }
  });

  const getConfigForPattern = () => {
    switch (selectedPattern) {
      case 'reflection': return reflectionConfig;
      case 'planning': return planningConfig;
      case 'tool-use': return toolUseConfig;
      case 'agentic-rag': return ragConfig;
      case 'metacognition': return metacognitionConfig;
      default: return {};
    }
  };

  const runPattern = async () => {
    setIsLoading(true);
    setError(null);
    setPatternData(null);
    setEvents([]);
    setFormCollapsed(true);

    // Open a WebSocket for live event streaming. Only accept events for
    // the currently-selected pattern (the channel is shared across runs).
    const backendPattern = PATTERN_EVENT_NAMES[selectedPattern];
    const wsUrl = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`;
    const ws = new WebSocket(`${wsUrl}/ws/patterns`);
    wsRef.current = ws;
    ws.onmessage = (msg) => {
      try {
        const evt = JSON.parse(msg.data);
        if (evt.type === 'pattern_event' && evt.pattern === backendPattern) {
          setEvents((prev) => [...prev, evt]);
        }
      } catch { /* ignore malformed frames */ }
    };
    ws.onerror = () => { /* non-fatal — HTTP result is still authoritative */ };

    try {
      const endpoint = `/api/patterns/${selectedPattern}`;
      const apiUrl = import.meta.env.VITE_API_URL || '';
      const response = await fetch(`${apiUrl}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(getConfigForPattern())
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`HTTP ${response.status}: ${detail}`);
      }

      const data = await response.json();
      setPatternData(data);
    } catch (err) {
      console.error('Error running pattern:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
      if (wsRef.current) {
        try { wsRef.current.close(); } catch { /* ignore */ }
        wsRef.current = null;
      }
    }
  };

  // -- Grid view (no pattern selected) --
  if (!selectedPattern) {
    return (
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Page Header */}
        <div className="flex items-center gap-4 mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-lg">
            <Sparkles className="text-white" size={32} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Agentic Design Patterns</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Configure and run real agent patterns — each spawns a live LLM agent and returns structured results
            </p>
          </div>
        </div>

        {/* Pattern Selection Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {PATTERNS.map((pattern) => {
            const Icon = pattern.icon;
            return (
              <button
                key={pattern.id}
                onClick={() => navigate(`/patterns/${pattern.id}`)}
                className="p-6 rounded-xl border-2 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 bg-white dark:bg-gray-900 hover:shadow-lg transition-all text-left"
              >
                <div className={`w-14 h-14 mb-4 rounded-xl flex items-center justify-center bg-gradient-to-br ${COLOR_CLASSES[pattern.color]} shadow-md`}>
                  <Icon className="text-white" size={28} />
                </div>
                <div className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-1">
                  {pattern.name}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {pattern.description}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  // -- Detail view (pattern selected) --
  const currentPattern = PATTERNS.find(p => p.id === selectedPattern);
  if (!currentPattern) {
    // Unknown pattern id — redirect back to grid
    return (
      <div className="max-w-7xl mx-auto p-6">
        <button
          onClick={() => navigate('/patterns')}
          className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 mb-4"
        >
          <ArrowLeft size={16} /> Back to patterns
        </button>
        <p className="text-gray-600 dark:text-gray-400">Unknown pattern: {selectedPattern}</p>
      </div>
    );
  }

  const PatternIcon = currentPattern.icon;

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Back Button */}
      <button
        onClick={() => navigate('/patterns')}
        className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
      >
        <ArrowLeft size={16} /> Back to patterns
      </button>

      {/* Pattern Header */}
      <div className="flex items-center gap-4 mb-2">
        <div className={`w-16 h-16 bg-gradient-to-br ${COLOR_CLASSES[currentPattern.color]} rounded-2xl flex items-center justify-center shadow-lg`}>
          <PatternIcon className="text-white" size={32} />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">{currentPattern.name}</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">{currentPattern.description}</p>
        </div>
      </div>

      {/* Pattern Configuration Form */}
      <div id="pattern-section-config" className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
        <div className={`flex items-center justify-between ${formCollapsed ? '' : 'mb-6'}`}>
          <button
            onClick={() => setFormCollapsed(!formCollapsed)}
            className="flex items-center gap-2 text-lg font-semibold text-gray-800 dark:text-gray-100 hover:text-gray-600 dark:hover:text-gray-300 transition"
          >
            {formCollapsed ? <ChevronRight size={20} /> : <ChevronDown size={20} />}
            Configuration
          </button>
          <button
            onClick={runPattern}
            disabled={isLoading}
            className={`
              px-6 py-2 rounded-lg font-medium flex items-center gap-2 transition-all
              ${isLoading
                ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:from-blue-600 hover:to-blue-700 shadow-md hover:shadow-lg'
              }
            `}
          >
            {isLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                <span>Running agent...</span>
              </>
            ) : (
              <>
                <Play size={16} />
                <span>Run Pattern</span>
              </>
            )}
          </button>
        </div>

        {/* Per-pattern form fields (hidden when collapsed) */}
        {!formCollapsed && (
          <>
            {selectedPattern === 'reflection' && (
              <ReflectionForm config={reflectionConfig} onChange={setReflectionConfig} />
            )}
            {selectedPattern === 'planning' && (
              <PlanningForm config={planningConfig} onChange={setPlanningConfig} />
            )}
            {selectedPattern === 'tool-use' && (
              <ToolUseForm config={toolUseConfig} onChange={setToolUseConfig} />
            )}
            {selectedPattern === 'agentic-rag' && (
              <RAGForm config={ragConfig} onChange={setRagConfig} />
            )}
            {selectedPattern === 'metacognition' && (
              <MetacognitionForm config={metacognitionConfig} onChange={setMetacognitionConfig} />
            )}
          </>
        )}
      </div>

      {/* Live Event Stream */}
      {(isLoading || events.length > 0) && (
        <div id="pattern-section-events" className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
          <button
            onClick={() => setEventsCollapsed((c) => !c)}
            className={`w-full flex items-center gap-2 ${eventsCollapsed ? '' : 'mb-4'} hover:opacity-80 transition`}
          >
            {eventsCollapsed ? <ChevronRight size={18} /> : <ChevronDown size={18} />}
            <Radio
              size={18}
              className={isLoading ? 'text-green-500 animate-pulse' : 'text-gray-400'}
            />
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
              Live Events
            </h2>
            <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
              {events.length} {events.length === 1 ? 'event' : 'events'}
            </span>
            {eventsCollapsed && events.length > 0 && (
              <span className="text-xs text-gray-500 dark:text-gray-400 ml-2 font-mono truncate">
                {summarizeEvents(events)}
              </span>
            )}
          </button>
          {!eventsCollapsed && (
            <div className="max-h-96 overflow-y-auto space-y-2 font-mono text-xs">
              {events.map((evt, idx) => (
                <EventRow key={idx} event={evt} />
              ))}
              {isLoading && events.length === 0 && (
                <div className="text-gray-500 dark:text-gray-400 italic">
                  Waiting for agent events...
                </div>
              )}
              <div ref={eventsEndRef} />
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div id="pattern-section-error" className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-xl p-4">
          <div className="text-sm font-medium text-red-800 dark:text-red-300">Error running pattern</div>
          <div className="text-sm text-red-700 dark:text-red-400 mt-1">{error}</div>
        </div>
      )}

      {/* Pattern Visualization */}
      {patternData && (
        <div id="pattern-section-results" className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-6">Execution Results</h2>

          {selectedPattern === 'reflection' && <ReflectionViz data={patternData} />}
          {selectedPattern === 'planning' && <PlanningViz data={patternData} />}
          {selectedPattern === 'agentic-rag' && <AgenticRAGViz data={patternData} />}

          {selectedPattern === 'tool-use' && (
            <div className="space-y-4">
              <div className="bg-orange-50 dark:bg-orange-950/30 p-4 rounded-lg border border-orange-200 dark:border-orange-800">
                <div className="font-semibold text-gray-800 dark:text-gray-100 mb-2">Task Analysis</div>
                <div className="text-sm text-gray-700 dark:text-gray-300 mb-3">{patternData.task}</div>
                <div className="flex flex-wrap gap-2">
                  {patternData.analysis?.required_capabilities?.map((req, idx) => (
                    <span key={idx} className="px-3 py-1 bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 rounded-full text-xs font-medium">
                      {req}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <div className="font-semibold text-gray-800 dark:text-gray-100 mb-3">Execution Plan</div>
                {patternData.execution_plan?.map((step, idx) => (
                  <div key={idx} className="mb-3 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 bg-orange-500 text-white rounded-full flex items-center justify-center font-bold text-sm">
                        {step.step}
                      </div>
                      <div className="flex-1">
                        <div className="font-medium text-gray-800 dark:text-gray-100 mb-1">{step.tool}</div>
                        <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">{step.action}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          <span className="font-medium">Input:</span> {step.input} →
                          <span className="font-medium ml-2">Output:</span> {step.output}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {selectedPattern === 'metacognition' && (
            <div className="space-y-4">
              <div className="bg-pink-50 dark:bg-pink-950/30 p-4 rounded-lg border border-pink-200 dark:border-pink-800">
                <div className="font-semibold text-gray-800 dark:text-gray-100 mb-3">Performance Assessment</div>
                <div className="text-lg font-bold text-pink-600 dark:text-pink-400 mb-2">
                  Overall Score: {(patternData.performance_assessment?.overall_score * 100).toFixed(0)}%
                </div>
                <div className="grid md:grid-cols-2 gap-4 mt-4">
                  <div>
                    <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">Strengths</div>
                    <ul className="space-y-1">
                      {patternData.performance_assessment?.strengths?.map((s, idx) => (
                        <li key={idx} className="text-sm text-green-700 dark:text-green-400">✓ {s}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">Weaknesses</div>
                    <ul className="space-y-1">
                      {patternData.performance_assessment?.weaknesses?.map((w, idx) => (
                        <li key={idx} className="text-sm text-red-700 dark:text-red-400">✗ {w}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              {patternData.strategy_adjustments?.length > 0 && (
                <div>
                  <div className="font-semibold text-gray-800 dark:text-gray-100 mb-3">Strategy Adjustments</div>
                  {patternData.strategy_adjustments.map((adj, idx) => (
                    <div key={idx} className="mb-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                      <div className="font-medium text-gray-800 dark:text-gray-100 mb-1">
                        {typeof adj === 'string' ? adj : (adj.aspect?.charAt(0).toUpperCase() + adj.aspect?.slice(1))}
                      </div>
                      {typeof adj !== 'string' && (
                        <>
                          <div className="text-sm text-gray-700 dark:text-gray-300 mb-1">{adj.suggestion}</div>
                          <div className="text-xs text-blue-600 dark:text-blue-400 font-medium">
                            Expected Impact: {adj.expected_impact}
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ==================== EVENT ROW ====================

/** Build a compact "eventName x3 · otherEvent x1" summary for the collapsed live feed */
function summarizeEvents(events) {
  const counts = {};
  for (const e of events) {
    const name = e.event || 'unknown';
    counts[name] = (counts[name] || 0) + 1;
  }
  return Object.entries(counts)
    .map(([name, n]) => `${name}${n > 1 ? ` x${n}` : ''}`)
    .join(' · ');
}

function EventRow({ event }) {
  const { event: name, timestamp, type, pattern, ...data } = event;
  const time = timestamp ? new Date(timestamp).toLocaleTimeString() : '';
  const hasData = Object.keys(data).length > 0;
  return (
    <div className="flex items-start gap-3 p-2 rounded bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-800">
      <span className="text-gray-400 dark:text-gray-500 flex-shrink-0">{time}</span>
      <span className="font-semibold text-blue-600 dark:text-blue-400 flex-shrink-0 min-w-[120px]">
        {name}
      </span>
      {hasData && (
        <span className="text-gray-600 dark:text-gray-400 break-all flex-1">
          {JSON.stringify(data)}
        </span>
      )}
    </div>
  );
}


// ==================== FORM COMPONENTS ====================

const inputClass = "w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none";
const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1";

function ReflectionForm({ config, onChange }) {
  const criteriaList = Object.entries(config.criteria);

  const updateCriteria = (newList) => {
    const obj = {};
    newList.forEach(([k, v]) => { obj[k] = v; });
    onChange({ ...config, criteria: obj });
  };
  const updateKey = (idx, newKey) => {
    const list = [...criteriaList];
    list[idx] = [newKey, list[idx][1]];
    updateCriteria(list);
  };
  const updateValue = (idx, newValue) => {
    const list = [...criteriaList];
    list[idx] = [list[idx][0], newValue];
    updateCriteria(list);
  };
  const removeCriterion = (idx) => {
    updateCriteria(criteriaList.filter((_, i) => i !== idx));
  };
  const addCriterion = () => {
    updateCriteria([...criteriaList, [`criterion_${criteriaList.length + 1}`, '']]);
  };

  return (
    <div className="space-y-4">
      <div>
        <label className={labelClass}>Initial Output</label>
        <textarea
          value={config.initial_output}
          onChange={(e) => onChange({ ...config, initial_output: e.target.value })}
          className={inputClass}
          rows={3}
          placeholder="Text to improve through reflection..."
        />
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">The agent will critique and iteratively improve this text</p>
      </div>
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className={labelClass + ' mb-0'}>Quality Criteria</label>
          <button onClick={addCriterion} className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
            <Plus size={12} /> Add
          </button>
        </div>
        <div className="space-y-2">
          {criteriaList.map(([key, value], idx) => (
            <div key={idx} className="group flex items-center gap-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2 border border-gray-200 dark:border-gray-700">
              <span className="text-xs font-semibold text-purple-600 dark:text-purple-400 bg-purple-100 dark:bg-purple-900/40 px-2 py-0.5 rounded flex-shrink-0 min-w-0">
                <input
                  value={key}
                  onChange={(e) => updateKey(idx, e.target.value)}
                  className="bg-transparent outline-none w-20 text-xs font-semibold text-purple-600 dark:text-purple-400"
                  placeholder="name"
                />
              </span>
              <input
                value={value}
                onChange={(e) => updateValue(idx, e.target.value)}
                className="flex-1 bg-transparent text-sm text-gray-700 dark:text-gray-300 outline-none min-w-0"
                placeholder="Description..."
              />
              <button onClick={() => removeCriterion(idx)} className="text-gray-300 dark:text-gray-600 hover:text-red-500 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PlanningForm({ config, onChange }) {
  const constraintList = Object.entries(config.constraints);

  const updateConstraints = (newList) => {
    const obj = {};
    newList.forEach(([k, v]) => { obj[k] = v; });
    onChange({ ...config, constraints: obj });
  };
  const updateKey = (idx, newKey) => {
    const list = [...constraintList];
    list[idx] = [newKey, list[idx][1]];
    updateConstraints(list);
  };
  const updateValue = (idx, newValue) => {
    const list = [...constraintList];
    list[idx] = [list[idx][0], newValue];
    updateConstraints(list);
  };
  const removeConstraint = (idx) => {
    updateConstraints(constraintList.filter((_, i) => i !== idx));
  };
  const addConstraint = () => {
    updateConstraints([...constraintList, [`constraint_${constraintList.length + 1}`, '']]);
  };

  return (
    <div className="space-y-4">
      <div>
        <label className={labelClass}>Goal</label>
        <textarea
          value={config.goal}
          onChange={(e) => onChange({ ...config, goal: e.target.value })}
          className={inputClass}
          rows={2}
          placeholder="What should the agent plan?"
        />
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">The agent will decompose this into actionable steps with dependencies and time estimates</p>
      </div>
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className={labelClass + ' mb-0'}>Constraints</label>
          <button onClick={addConstraint} className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
            <Plus size={12} /> Add
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {constraintList.map(([key, value], idx) => (
            <div key={idx} className="group flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg pl-1 pr-1 py-1">
              <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/40 px-2 py-0.5 rounded">
                <input
                  value={key}
                  onChange={(e) => updateKey(idx, e.target.value)}
                  className="bg-transparent outline-none w-16 text-xs font-semibold text-blue-600 dark:text-blue-400"
                  placeholder="key"
                />
              </span>
              <input
                value={value}
                onChange={(e) => updateValue(idx, e.target.value)}
                className="bg-transparent text-sm text-gray-800 dark:text-gray-100 outline-none w-24"
                placeholder="value"
              />
              <button onClick={() => removeConstraint(idx)} className="text-gray-400 hover:text-red-500 p-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ToolUseForm({ config, onChange }) {
  const updateTool = (idx, value) => {
    const tools = [...config.available_tools];
    tools[idx] = value;
    onChange({ ...config, available_tools: tools });
  };
  const removeTool = (idx) => {
    onChange({ ...config, available_tools: config.available_tools.filter((_, i) => i !== idx) });
  };
  const addTool = () => {
    onChange({ ...config, available_tools: [...config.available_tools, ''] });
  };

  return (
    <div className="space-y-4">
      <div>
        <label className={labelClass}>Task</label>
        <textarea
          value={config.task}
          onChange={(e) => onChange({ ...config, task: e.target.value })}
          className={inputClass}
          rows={2}
          placeholder="What task should the agent accomplish?"
        />
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">The agent will analyze this task and select the best tools for the job</p>
      </div>
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className={labelClass + ' mb-0'}>Available Tools</label>
          <button onClick={addTool} className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
            <Plus size={12} /> Add tool
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {config.available_tools.map((tool, idx) => (
            <div key={idx} className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg pl-3 pr-1 py-1">
              <input
                value={tool}
                onChange={(e) => updateTool(idx, e.target.value)}
                className="bg-transparent text-sm text-gray-800 dark:text-gray-100 outline-none w-28"
                placeholder="tool_name"
              />
              <button onClick={() => removeTool(idx)} className="text-gray-400 hover:text-red-500 p-1">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function RAGForm({ config, onChange }) {
  return (
    <div className="space-y-4">
      <div>
        <label className={labelClass}>Search Query</label>
        <input
          value={config.query}
          onChange={(e) => onChange({ ...config, query: e.target.value })}
          className={inputClass}
          placeholder="What should the agent search for?"
        />
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">The agent will iteratively refine this query and evaluate document relevance</p>
      </div>
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Max Refinements</label>
        <div className="flex items-center gap-2">
          {[1, 2, 3, 5, 10].map((n) => (
            <button
              key={n}
              onClick={() => onChange({ ...config, max_refinements: n })}
              className={`w-9 h-9 rounded-lg text-sm font-medium transition-all ${
                config.max_refinements === n
                  ? 'bg-green-500 text-white shadow-md'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function MetacognitionForm({ config, onChange }) {
  const statusColors = {
    success: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400',
    error: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400',
    timeout: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-400',
  };

  const updateTrace = (idx, field, value) => {
    const trace = [...config.execution_trace];
    trace[idx] = { ...trace[idx], [field]: field === 'duration' ? parseFloat(value) || 0 : value };
    onChange({ ...config, execution_trace: trace });
  };
  const removeTrace = (idx) => {
    onChange({ ...config, execution_trace: config.execution_trace.filter((_, i) => i !== idx) });
  };
  const addTrace = () => {
    onChange({ ...config, execution_trace: [...config.execution_trace, { step: '', status: 'success', duration: 1.0 }] });
  };
  const updateMetric = (key, value) => {
    onChange({ ...config, performance_metrics: { ...config.performance_metrics, [key]: parseFloat(value) || 0 } });
  };

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className={labelClass + ' mb-0'}>Execution Trace</label>
          <button onClick={addTrace} className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
            <Plus size={12} /> Add step
          </button>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Simulated agent execution history for the metacognition agent to analyze</p>
        <div className="space-y-2">
          {config.execution_trace.map((entry, idx) => (
            <div key={idx} className="group flex items-center gap-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2 border border-gray-200 dark:border-gray-700">
              <span className="text-xs text-gray-400 dark:text-gray-500 w-5 text-center flex-shrink-0">{idx + 1}</span>
              <input
                value={entry.step}
                onChange={(e) => updateTrace(idx, 'step', e.target.value)}
                className="bg-transparent text-sm text-gray-800 dark:text-gray-100 outline-none flex-1 min-w-0"
                placeholder="Step name"
              />
              <select
                value={entry.status}
                onChange={(e) => updateTrace(idx, 'status', e.target.value)}
                className={`text-xs font-medium rounded-full px-2.5 py-1 border-0 outline-none cursor-pointer ${statusColors[entry.status] || statusColors.success}`}
              >
                <option value="success">success</option>
                <option value="error">error</option>
                <option value="timeout">timeout</option>
              </select>
              <div className="flex items-center gap-1 flex-shrink-0">
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={entry.duration}
                  onChange={(e) => updateTrace(idx, 'duration', e.target.value)}
                  className="bg-transparent text-sm text-gray-600 dark:text-gray-400 outline-none w-12 text-right"
                />
                <span className="text-xs text-gray-400 dark:text-gray-500">s</span>
              </div>
              <button onClick={() => removeTrace(idx)} className="text-gray-300 dark:text-gray-600 hover:text-red-500 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
      <div>
        <label className={labelClass}>Performance Metrics</label>
        <div className="flex gap-4">
          {Object.entries(config.performance_metrics).map(([key, value]) => (
            <div key={key} className="flex-1 bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 border border-gray-200 dark:border-gray-700 text-center">
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={value}
                onChange={(e) => updateMetric(key, e.target.value)}
                className="bg-transparent text-2xl font-bold text-pink-600 dark:text-pink-400 outline-none w-full text-center"
              />
              <div className="text-xs text-gray-500 dark:text-gray-400 capitalize mt-1">{key}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
