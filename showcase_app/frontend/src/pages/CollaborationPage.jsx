import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { collaborationAPI, agentExecutionsAPI } from '../services/api'
import toast from 'react-hot-toast'
import {
  Users,
  MessageSquare,
  GitBranch,
  Play,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  Clock,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Shield,
  Share2,
  FileText,
  Loader2,
  History,
} from 'lucide-react'

// URL slug <-> internal pattern id (only difference is hyphen vs underscore)
const urlToId = (slug) => slug.replace(/-/g, '_')
const idToUrl = (id) => id.replace(/_/g, '-')

const PATTERN_ICONS = {
  consensus: <CheckCircle2 size={28} />,
  debate: <Shield size={28} />,
  hierarchical: <GitBranch size={28} />,
  peer_to_peer: <Share2 size={28} />,
}

const PATTERN_COLORS = {
  consensus: 'from-emerald-500 to-teal-600',
  debate: 'from-red-500 to-orange-600',
  hierarchical: 'from-blue-500 to-indigo-600',
  peer_to_peer: 'from-purple-500 to-pink-600',
}

const PATTERN_BG = {
  consensus: 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800',
  debate: 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800',
  hierarchical: 'bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800',
  peer_to_peer: 'bg-purple-50 dark:bg-purple-950/30 border-purple-200 dark:border-purple-800',
}

const DEFAULT_CONFIGS = {
  consensus: {
    topic: 'We should adopt a microservices architecture for our next project',
    agents: ['Analyst', 'Engineer', 'Designer', 'PM', 'QA'],
    strategy: 'majority',
    max_iterations: 3,
  },
  debate: {
    topic: 'AI systems should be open source by default',
    proponents: ['Advocate-Open', 'Advocate-Community'],
    opponents: ['Skeptic-Security', 'Skeptic-Business'],
    moderator: 'Moderator',
    rounds: 2,
  },
  hierarchical: {
    task: 'Analyze market trends in the AI sector and produce a summary report',
    leader: 'Project-Lead',
    workers: ['Researcher-Alpha', 'Analyst-Beta', 'Writer-Gamma'],
  },
  peer_to_peer: {
    task: 'Brainstorm innovative product ideas for AI-powered developer tools',
    peers: ['Alice', 'Bob', 'Carol', 'Dave'],
    rounds: 2,
  },
}

export default function CollaborationPage() {
  const { patternId: urlPatternId } = useParams()
  const navigate = useNavigate()
  const selectedPattern = urlPatternId ? urlToId(urlPatternId) : null
  const [configs, setConfigs] = useState(DEFAULT_CONFIGS)
  const [results, setResults] = useState({})
  const [expandedSteps, setExpandedSteps] = useState({})
  const [liveSteps, setLiveSteps] = useState([]) // WS-streamed steps during a run
  const [activeRunId, setActiveRunId] = useState(null)
  const [formCollapsed, setFormCollapsed] = useState(false)
  const wsRef = useRef(null)

  const { data: patternsData } = useQuery({
    queryKey: ['collaboration-patterns'],
    queryFn: async () => {
      const response = await collaborationAPI.getPatterns()
      return response.data
    },
  })

  // Fetch previous collaboration executions
  const { data: execData, refetch: refetchExecs } = useQuery({
    queryKey: ['collaboration-executions', selectedPattern],
    queryFn: async () => {
      const response = await collaborationAPI.getExecutions(selectedPattern)
      return response.data
    },
    enabled: !!selectedPattern,
    refetchInterval: 15000,
  })

  // WebSocket connection for real-time collaboration updates.
  // StrictMode double-invokes this effect in dev, so the cleanup must
  // close the socket regardless of readyState (CONNECTING or OPEN) —
  // otherwise the first instance stays alive and every `collab_step`
  // message is delivered twice, duplicating live timeline rows.
  useEffect(() => {
    const wsUrl = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`
    let ws
    let cancelled = false

    try {
      ws = new WebSocket(`${wsUrl}/ws/collaboration`)
      wsRef.current = ws

      ws.onmessage = (event) => {
        if (cancelled) return
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'collab_step' && msg.run_id) {
            setLiveSteps((prev) => [...prev, msg])
          }
          if (msg.type === 'collab_complete' && msg.run_id) {
            setActiveRunId(null)
            refetchExecs()
          }
        } catch {}
      }

      ws.onerror = () => {}
      ws.onclose = () => { if (wsRef.current === ws) wsRef.current = null }
    } catch {}

    return () => {
      cancelled = true
      if (!ws) return
      // Close whether still connecting or already open — StrictMode
      // cleanup fires before OPEN, so readyState==OPEN guard leaks the socket.
      if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [refetchExecs])

  const mutationOpts = (fn, key) => ({
    mutationFn: fn,
    onMutate: () => {
      setLiveSteps([])
      setActiveRunId('pending')
    },
    onSuccess: (response) => {
      setResults((prev) => ({ ...prev, [key]: response.data }))
      setActiveRunId(null)
      setLiveSteps([])
      refetchExecs()
    },
    onError: (err) => {
      setActiveRunId(null)
      toast.error(`${key} failed: ${err.message}`)
    },
  })

  const consensusMutation = useMutation(mutationOpts((d) => collaborationAPI.runConsensus(d), 'consensus'))
  const debateMutation = useMutation(mutationOpts((d) => collaborationAPI.runDebate(d), 'debate'))
  const hierarchicalMutation = useMutation(mutationOpts((d) => collaborationAPI.runHierarchical(d), 'hierarchical'))
  const peerToPeerMutation = useMutation(mutationOpts((d) => collaborationAPI.runPeerToPeer(d), 'peer_to_peer'))

  const mutations = {
    consensus: consensusMutation,
    debate: debateMutation,
    hierarchical: hierarchicalMutation,
    peer_to_peer: peerToPeerMutation,
  }

  const handleRun = (patternId) => {
    const config = configs[patternId]
    setFormCollapsed(true)
    mutations[patternId].mutate(config)
  }

  const updateConfig = (patternId, field, value) => {
    setConfigs((prev) => ({
      ...prev,
      [patternId]: { ...prev[patternId], [field]: value },
    }))
  }

  const toggleStep = (key) => {
    setExpandedSteps((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const patterns = patternsData?.patterns || []
  const isRunning = (id) => mutations[id]?.isPending
  const prevExecutions = execData?.executions || []

  // -- Grid view (no pattern selected) --
  if (!selectedPattern) {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">
            Agent Collaboration Patterns
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Explore four collaboration patterns from ia_modules: how agents work together to solve problems
          </p>
        </div>

        {/* Pattern Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {patterns.map((pattern) => (
            <button
              key={pattern.id}
              onClick={() => navigate(`/collaboration/${idToUrl(pattern.id)}`)}
              className="text-left p-5 rounded-xl border-2 transition-all duration-200 bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md"
            >
              <div className={`inline-flex p-3 rounded-xl bg-gradient-to-br ${PATTERN_COLORS[pattern.id]} text-white mb-3`}>
                {PATTERN_ICONS[pattern.id]}
              </div>
              <h3 className="text-lg font-bold text-gray-800 dark:text-gray-100">{pattern.name}</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                {pattern.description}
              </p>
              <div className="flex flex-wrap gap-1 mt-3">
                {(pattern.use_cases || []).slice(0, 2).map((uc, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                    {uc}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </div>
    )
  }

  // -- Detail view (pattern selected) --
  const currentPattern = patterns.find((p) => p.id === selectedPattern)

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <button
        onClick={() => navigate('/collaboration')}
        className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
      >
        <ArrowLeft size={16} /> Back to collaboration patterns
      </button>

      {/* Pattern Header */}
      <div className="flex items-center gap-4">
        <div className={`inline-flex p-3 rounded-xl bg-gradient-to-br ${PATTERN_COLORS[selectedPattern]} text-white`}>
          {PATTERN_ICONS[selectedPattern]}
        </div>
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">
            {currentPattern?.name || selectedPattern}
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {currentPattern?.description || ''}
          </p>
        </div>
      </div>

      {/* Selected Pattern Configuration & Run */}
      <div className={`rounded-xl border-2 overflow-hidden ${PATTERN_BG[selectedPattern]}`}>
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setFormCollapsed((c) => !c)}
              className="flex items-center gap-2 text-xl font-bold text-gray-800 dark:text-gray-100 hover:text-gray-600 dark:hover:text-gray-300 transition"
            >
              {formCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
              Configure & Run: {currentPattern?.name}
            </button>
            <button
              onClick={() => handleRun(selectedPattern)}
              disabled={isRunning(selectedPattern)}
              className={`
                flex items-center gap-2 px-5 py-2.5 rounded-xl text-white font-medium
                bg-gradient-to-r ${PATTERN_COLORS[selectedPattern]}
                hover:opacity-90 disabled:opacity-50 transition-all shadow-lg
              `}
            >
              {isRunning(selectedPattern) ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play size={18} />
                  Run
                </>
              )}
            </button>
          </div>

          {/* Pattern-specific config forms */}
          {!formCollapsed && (
            <>
              {selectedPattern === 'consensus' && (
                <ConsensusConfig config={configs.consensus} onChange={(f, v) => updateConfig('consensus', f, v)} />
              )}
              {selectedPattern === 'debate' && (
                <DebateConfig config={configs.debate} onChange={(f, v) => updateConfig('debate', f, v)} />
              )}
              {selectedPattern === 'hierarchical' && (
                <HierarchicalConfig config={configs.hierarchical} onChange={(f, v) => updateConfig('hierarchical', f, v)} />
              )}
              {selectedPattern === 'peer_to_peer' && (
                <PeerToPeerConfig config={configs.peer_to_peer} onChange={(f, v) => updateConfig('peer_to_peer', f, v)} />
              )}
            </>
          )}
        </div>
      </div>

      {/* Results — single timeline source: live WS stream while running, full history once complete */}
      {(isRunning(selectedPattern) || results[selectedPattern]) && (() => {
        const running = isRunning(selectedPattern)
        const timeline = annotateRounds(
          running ? liveSteps : (results[selectedPattern]?.history || [])
        )
        return (
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="p-6">
              <div className="flex items-center gap-2 mb-4">
                {running && <Loader2 size={18} className="animate-spin text-blue-500" />}
                <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">
                  {running ? 'Running...' : 'Results'}
                </h2>
                <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                  {timeline.length} step{timeline.length === 1 ? '' : 's'}
                </span>
              </div>
              {!running && results[selectedPattern] && (
                <ResultSummary result={results[selectedPattern]} patternId={selectedPattern} />
              )}
              <div className="mt-4 space-y-2">
                {timeline.map((step, idx) => {
                  const key = `${selectedPattern}_${idx}_${step.phase || ''}_${step.agent || ''}`
                  return (
                    <StepAccordion
                      key={key}
                      step={step}
                      stepKey={key}
                      isExpanded={
                        expandedSteps[key] ?? (running && idx === timeline.length - 1)
                      }
                      onToggle={toggleStep}
                    />
                  )
                })}
              </div>
            </div>
          </div>
        )
      })()}

      {/* Previous Executions */}
      {prevExecutions.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <History size={18} className="text-gray-500" />
              <h2 className="text-lg font-bold text-gray-800 dark:text-gray-100">Previous Executions</h2>
            </div>
            <div className="space-y-2">
              {prevExecutions.map((exec) => (
                <PreviousExecutionRow key={exec.job_id} exec={exec} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


// ==================== Live Step Row (WS streamed) ====================


// ==================== Previous Execution Row ====================

function PreviousExecutionRow({ exec }) {
  const [expanded, setExpanded] = useState(false)
  const [fullResult, setFullResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [expandedSteps, setExpandedSteps] = useState({})

  const handleExpand = async () => {
    if (expanded) {
      setExpanded(false)
      return
    }
    setExpanded(true)
    if (fullResult === null) {
      setLoading(true)
      try {
        const resp = await collaborationAPI.getExecution(exec.job_id)
        setFullResult(resp.data)
      } catch {
        setFullResult({ history: [], result: {} })
      }
      setLoading(false)
    }
  }

  const toggleStep = (key) => {
    setExpandedSteps((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const statusColor = exec.status === 'completed'
    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
    : exec.status === 'failed'
    ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
    : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400'

  const patternId = fullResult?.pattern || exec.agent_role

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={handleExpand}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition text-left"
      >
        <div className="flex items-center gap-3">
          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusColor}`}>
            {exec.status}
          </span>
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {exec.agent_role}
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {exec.started_at ? new Date(exec.started_at).toLocaleString() : ''}
          </span>
          {exec.duration_seconds && (
            <span className="text-xs text-gray-400">
              {exec.duration_seconds.toFixed(1)}s
            </span>
          )}
        </div>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {expanded && (
        <div className="px-4 py-3 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 space-y-4">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 size={16} className="animate-spin" /> Loading...
            </div>
          )}

          {fullResult && (
            <>
              {/* Same ResultSummary cards as the live run */}
              <ResultSummary result={fullResult} patternId={patternId} />

              {/* Same accordion timeline as the live run */}
              <div className="space-y-2">
                {annotateRounds(fullResult.history || []).map((step, idx) => (
                  <StepAccordion
                    key={`prev_${exec.job_id}_${idx}`}
                    step={step}
                    stepKey={`prev_${exec.job_id}_${idx}`}
                    isExpanded={expandedSteps[`prev_${exec.job_id}_${idx}`]}
                    onToggle={toggleStep}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}


// ==================== NDJSON Events Panel (loads events for a job_id) ====================

function NdjsonEventsPanel({ jobId }) {
  const [events, setEvents] = useState(null)
  const [expanded, setExpanded] = useState(false)

  const loadEvents = async () => {
    if (events !== null) {
      setExpanded(!expanded)
      return
    }
    try {
      const resp = await agentExecutionsAPI.getEvents(jobId, { limit: 50 })
      setEvents(resp.data?.events || resp.data || [])
      setExpanded(true)
    } catch {
      setEvents([])
      setExpanded(true)
    }
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={loadEvents}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition text-left"
      >
        <div className="flex items-center gap-2">
          <FileText size={14} className="text-blue-500" />
          <span className="text-xs font-mono text-gray-600 dark:text-gray-400">{jobId.slice(0, 8)}...</span>
          {events && <span className="text-[10px] text-gray-400">{events.length} events</span>}
        </div>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {expanded && events && (
        <div className="px-3 py-2 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 space-y-1 max-h-64 overflow-y-auto">
          {events.length === 0 && (
            <p className="text-xs text-gray-400 py-2">No events found</p>
          )}
          {events.map((evt, i) => (
            <NdjsonEventRow key={i} event={evt} />
          ))}
        </div>
      )}
    </div>
  )
}


// ==================== Single NDJSON Event Row ====================

const EVENT_COLORS = {
  text: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  tool_use: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  tool_result: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  reasoning: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400',
  system: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
  step_start: 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-400',
  step_finish: 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-400',
}

function NdjsonEventRow({ event }) {
  const [showRaw, setShowRaw] = useState(false)
  const etype = event.type || 'unknown'
  const colorClass = EVENT_COLORS[etype] || EVENT_COLORS.system

  const preview = event.text
    || event.result
    || (event.tool ? `${event.tool}(${event.tool_use_id || ''})` : '')
    || event.subtype
    || etype

  return (
    <div>
      <button
        onClick={() => setShowRaw(!showRaw)}
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition"
      >
        <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${colorClass}`}>
          {etype}
        </span>
        {event.step_name && (
          <span className="text-[10px] text-gray-400 font-mono">{event.step_name}</span>
        )}
        <span className="text-xs text-gray-600 dark:text-gray-400 truncate flex-1">
          {String(preview).slice(0, 120)}
        </span>
      </button>
      {showRaw && (
        <pre className="text-[10px] text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 px-3 py-2 rounded mt-1 whitespace-pre-wrap overflow-x-auto max-h-48 overflow-y-auto">
          {JSON.stringify(event, null, 2)}
        </pre>
      )}
    </div>
  )
}


// ==================== Config Forms ====================

function ConsensusConfig({ config, onChange }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="md:col-span-2">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Proposal / Topic</label>
        <textarea
          value={config.topic}
          onChange={(e) => onChange('topic', e.target.value)}
          rows={2}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Agents (comma-separated)</label>
        <input
          type="text"
          value={config.agents.join(', ')}
          onChange={(e) => onChange('agents', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
        />
      </div>
      <div className="flex gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Strategy</label>
          <select
            value={config.strategy}
            onChange={(e) => onChange('strategy', e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          >
            <option value="majority">Majority</option>
            <option value="unanimous">Unanimous</option>
            <option value="supermajority">Supermajority</option>
            <option value="weighted">Weighted</option>
          </select>
        </div>
        <div className="w-32">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Iterations</label>
          <input
            type="number"
            min={1}
            max={10}
            value={config.max_iterations}
            onChange={(e) => onChange('max_iterations', parseInt(e.target.value) || 3)}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>
      </div>
    </div>
  )
}

function DebateConfig({ config, onChange }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="md:col-span-2">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Debate Topic</label>
        <textarea
          value={config.topic}
          onChange={(e) => onChange('topic', e.target.value)}
          rows={2}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-red-500 focus:border-red-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Proponents (comma-separated)</label>
        <input
          type="text"
          value={config.proponents.join(', ')}
          onChange={(e) => onChange('proponents', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-red-500 focus:border-red-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Opponents (comma-separated)</label>
        <input
          type="text"
          value={config.opponents.join(', ')}
          onChange={(e) => onChange('opponents', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-red-500 focus:border-red-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Moderator</label>
        <input
          type="text"
          value={config.moderator}
          onChange={(e) => onChange('moderator', e.target.value)}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-red-500 focus:border-red-500"
        />
      </div>
      <div className="w-32">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Rounds</label>
        <input
          type="number"
          min={1}
          max={5}
          value={config.rounds}
          onChange={(e) => onChange('rounds', parseInt(e.target.value) || 2)}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-red-500 focus:border-red-500"
        />
      </div>
    </div>
  )
}

function HierarchicalConfig({ config, onChange }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="md:col-span-2">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Task</label>
        <textarea
          value={config.task}
          onChange={(e) => onChange('task', e.target.value)}
          rows={2}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Leader</label>
        <input
          type="text"
          value={config.leader}
          onChange={(e) => onChange('leader', e.target.value)}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Workers (comma-separated)</label>
        <input
          type="text"
          value={config.workers.join(', ')}
          onChange={(e) => onChange('workers', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
    </div>
  )
}

function PeerToPeerConfig({ config, onChange }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="md:col-span-2">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Collaborative Task</label>
        <textarea
          value={config.task}
          onChange={(e) => onChange('task', e.target.value)}
          rows={2}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Peers (comma-separated)</label>
        <input
          type="text"
          value={config.peers.join(', ')}
          onChange={(e) => onChange('peers', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
        />
      </div>
      <div className="w-32">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Rounds</label>
        <input
          type="number"
          min={1}
          max={5}
          value={config.rounds}
          onChange={(e) => onChange('rounds', parseInt(e.target.value) || 2)}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
        />
      </div>
    </div>
  )
}


function ResultSummary({ result, patternId }) {
  if (patternId === 'consensus') {
    const r = result.result || {}
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Consensus"
          value={r.consensus_reached ? 'Reached' : 'Not Reached'}
          icon={r.consensus_reached ? <CheckCircle size={20} className="text-green-500" /> : <XCircle size={20} className="text-red-500" />}
        />
        <SummaryCard
          label="Agreement"
          value={`${((r.agreement_level || 0) * 100).toFixed(0)}%`}
          icon={<Users size={20} className="text-emerald-500" />}
        />
        <SummaryCard
          label="Strategy"
          value={result.strategy || 'N/A'}
          icon={<CheckCircle2 size={20} className="text-teal-500" />}
        />
        <SummaryCard
          label="Iterations"
          value={r.iterations || 0}
          icon={<Clock size={20} className="text-gray-500" />}
        />
      </div>
    )
  }

  if (patternId === 'debate') {
    const r = result.result || {}
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Status"
          value={r.status || 'completed'}
          icon={<CheckCircle size={20} className="text-green-500" />}
        />
        <SummaryCard
          label="Rounds"
          value={r.total_rounds || 0}
          icon={<Shield size={20} className="text-red-500" />}
        />
        <SummaryCard
          label="Arguments"
          value={r.total_arguments || 0}
          icon={<MessageSquare size={20} className="text-orange-500" />}
        />
        <SummaryCard
          label="Key Points"
          value={(r.proponent_key_points?.length || 0) + (r.opponent_key_points?.length || 0)}
          icon={<ArrowRight size={20} className="text-gray-500" />}
        />
      </div>
    )
  }

  if (patternId === 'hierarchical') {
    const r = result.result || {}
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Status"
          value={r.status || 'unknown'}
          icon={r.status === 'success' ? <CheckCircle size={20} className="text-green-500" /> : <XCircle size={20} className="text-yellow-500" />}
        />
        <SummaryCard
          label="Total Workers"
          value={r.total_workers || 0}
          icon={<Users size={20} className="text-blue-500" />}
        />
        <SummaryCard
          label="Successful"
          value={r.successful_workers || 0}
          icon={<CheckCircle size={20} className="text-green-500" />}
        />
        <SummaryCard
          label="Failed"
          value={r.failed_workers || 0}
          icon={<XCircle size={20} className="text-red-500" />}
        />
      </div>
    )
  }

  if (patternId === 'peer_to_peer') {
    const r = result.result || {}
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Status"
          value={r.status || 'unknown'}
          icon={<CheckCircle size={20} className="text-green-500" />}
        />
        <SummaryCard
          label="Peers"
          value={r.total_peers || 0}
          icon={<Users size={20} className="text-purple-500" />}
        />
        <SummaryCard
          label="Contributions"
          value={r.total_contributions || 0}
          icon={<MessageSquare size={20} className="text-pink-500" />}
        />
        <SummaryCard
          label="Rounds"
          value={r.rounds_completed || 0}
          icon={<Clock size={20} className="text-gray-500" />}
        />
      </div>
    )
  }

  return null
}

function SummaryCard({ label, value, icon }) {
  return (
    <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
      {icon}
      <div>
        <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
        <p className="text-sm font-bold text-gray-800 dark:text-gray-200 capitalize">{String(value)}</p>
      </div>
    </div>
  )
}


// ==================== Step Accordion (shared by live + previous) ====================

function StepAccordion({ step, stepKey, isExpanded, onToggle }) {
  const phaseColor = getPhaseColor(step.phase)
  const summary = stepSummary(step)
  const fullMsg = cleanMessage(step.message || '')

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      {/* Clickable header — short summary only */}
      <button
        onClick={() => onToggle(stepKey)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium shrink-0 ${phaseColor}`}>
            {formatPhase(step.phase)}
          </span>
          <span className="text-sm text-gray-700 dark:text-gray-300 truncate">
            {summary}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          {step.agent && (
            <span className="text-xs px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
              {step.agent}
            </span>
          )}
          {step.job_id && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-mono">
              NDJSON
            </span>
          )}
          {step.side && (
            <span className={`text-xs px-2 py-0.5 rounded ${
              step.side === 'proponent' || step.side === 'proponents'
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
            }`}>
              {step.side}
            </span>
          )}
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {/* Expanded detail — selectable text */}
      {isExpanded && (
        <div className="px-4 py-3 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 space-y-3">
          {fullMsg && fullMsg !== summary && (
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap select-text">
              {fullMsg}
            </p>
          )}
          <StepDetail step={step} />
          {step.job_id && <NdjsonEventsPanel jobId={step.job_id} />}
        </div>
      )}
    </div>
  )
}


// ==================== Helpers ====================

function getPhaseColor(phase) {
  if (phase.includes('setup')) return 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
  if (phase.includes('initialization')) return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
  if (phase.includes('voting') || phase.includes('vote')) return 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400'
  if (phase.includes('proposal')) return 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-400'
  if (phase.includes('opening')) return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
  if (phase.includes('closing')) return 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400'
  if (phase.includes('argument') || phase.includes('round')) return 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400'
  if (phase.includes('result')) return 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400'
  if (phase.includes('error')) return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
  if (phase.includes('worker') || phase.includes('task')) return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
  if (phase.includes('contribution')) return 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400'
  if (phase.includes('complete')) return 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400'
  return 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
}

function formatPhase(phase) {
  return phase
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Strip markdown code fences and parse embedded JSON into plain text */
function cleanMessage(msg) {
  if (!msg || typeof msg !== 'string') return msg || ''
  // Strip ```json ... ``` blocks — extract the JSON inside
  let cleaned = msg.replace(/```(?:json)?\s*([\s\S]*?)```/g, (_, inner) => {
    try {
      const obj = JSON.parse(inner.trim())
      // Convert JSON object to readable key: value lines
      return Object.entries(obj)
        .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
        .join('\n')
    } catch {
      return inner.trim()
    }
  })
  return cleaned.trim()
}

/** Get a short one-line summary for the accordion header */
function stepSummary(step) {
  const raw = step.message || step.phase || ''
  const clean = cleanMessage(raw)
  // Take first line, cap at 120 chars
  const firstLine = clean.split('\n')[0]
  const capped = firstLine.length > 120 ? firstLine.slice(0, 117) + '...' : firstLine
  // Prefix with round/iteration context so repeated step_complete rows across
  // rounds are visually distinct (backend reuses the same summary per round).
  return step._roundLabel ? `${step._roundLabel} · ${capped}` : capped
}

/**
 * Walk a flat history array and tag each step with a derived `_roundLabel`
 * based on the most recent round/iteration marker phase seen. This lets the
 * accordion distinguish otherwise-identical step_complete rows across rounds
 * without needing a backend change.
 */
function annotateRounds(steps) {
  let currentLabel = null
  return steps.map((step) => {
    const phase = step.phase || ''
    // Match phases like "round_1_opening", "voting_round_2", "round_3_start"
    const m = phase.match(/round[_\s]*(\d+)|voting_round_(\d+)/i)
    if (m) {
      const n = m[1] || m[2]
      currentLabel = `Round ${n}`
    }
    return currentLabel ? { ...step, _roundLabel: currentLabel } : step
  })
}

function StepDetail({ step }) {
  // Strip meta fields already shown in the accordion header
  const { phase, message, timestamp, run_id, job_id, ...data } = step
  const entries = Object.entries(data).filter(([, v]) => v !== null && v !== undefined && v !== '')

  if (entries.length === 0) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 italic">
        {message || phase || 'No additional details'}
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {entries.map(([key, val]) => (
        <div key={key}>
          <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase block mb-1">
            {key.replace(/_/g, ' ')}
          </span>
          {typeof val === 'string' ? (
            <p className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800/50 rounded-lg px-3 py-2 whitespace-pre-wrap">
              {val}
            </p>
          ) : Array.isArray(val) ? (
            <div className="space-y-1">
              {val.map((item, i) => (
                <div key={i} className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800/50 rounded px-3 py-1.5">
                  {typeof item === 'string' ? item : JSON.stringify(item, null, 2)}
                </div>
              ))}
            </div>
          ) : typeof val === 'object' ? (
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg px-3 py-2 space-y-1">
              {Object.entries(val).map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <span className="text-xs text-gray-500 dark:text-gray-400 font-mono min-w-[100px]">{k}:</span>
                  <span className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                    {typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800/50 rounded-lg px-3 py-2">
              {String(val)}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
