import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { agentExecutionsAPI } from '../services/api'
import {
  Play, CheckCircle, XCircle, Clock, ChevronDown, ChevronUp,
  FileText, Wrench, MessageSquare, AlertCircle, RefreshCw,
  Search, Filter,
} from 'lucide-react'

const STATUS_STYLES = {
  running: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  completed: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  failed: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
}

const STATUS_ICONS = {
  running: <Play size={14} />,
  completed: <CheckCircle size={14} />,
  failed: <XCircle size={14} />,
}

export default function AgentExecutionsPage() {
  const [selectedJobId, setSelectedJobId] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')

  const { data: listData, refetch: refetchList } = useQuery({
    queryKey: ['agent-executions', statusFilter, roleFilter],
    queryFn: async () => {
      const params = {}
      if (statusFilter) params.status = statusFilter
      if (roleFilter) params.role = roleFilter
      const res = await agentExecutionsAPI.list(params)
      return res.data
    },
    refetchInterval: 10000,
  })

  const { data: eventsData } = useQuery({
    queryKey: ['agent-events', selectedJobId],
    queryFn: async () => {
      if (!selectedJobId) return null
      const [eventsRes, summaryRes] = await Promise.all([
        agentExecutionsAPI.getEvents(selectedJobId, { limit: 500 }),
        agentExecutionsAPI.getSummary(selectedJobId),
      ])
      return { events: eventsRes.data.events, summary: summaryRes.data }
    },
    enabled: !!selectedJobId,
  })

  const executions = listData?.executions || []

  const handleScan = async () => {
    await agentExecutionsAPI.scan()
    refetchList()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Agent Executions</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Browse agent runs and inspect NDJSON event logs</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleScan}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 text-sm font-medium transition"
          >
            <RefreshCw size={16} />
            Scan Logs
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <Filter size={14} />
          <span>Filter:</span>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
        >
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
        >
          <option value="">All roles</option>
          <option value="researcher">Researcher</option>
          <option value="analyst">Analyst</option>
          <option value="writer">Writer</option>
          <option value="executor">Executor</option>
          <option value="planner">Planner</option>
          <option value="critic">Critic</option>
        </select>
        <span className="text-sm text-gray-400 dark:text-gray-500 ml-2">
          {executions.length} execution{executions.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Execution List */}
        <div className="lg:col-span-1 space-y-2 max-h-[70vh] overflow-y-auto">
          {executions.length === 0 && (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              <FileText size={48} className="mx-auto mb-3 opacity-50" />
              <p>No agent executions found</p>
              <p className="text-sm mt-1">Run an agent or click Scan Logs</p>
            </div>
          )}
          {executions.map((exec) => (
            <button
              key={exec.job_id}
              onClick={() => setSelectedJobId(exec.job_id)}
              className={`w-full text-left p-4 rounded-xl border transition-all ${
                selectedJobId === exec.job_id
                  ? 'border-primary-500 bg-primary-50/50 dark:bg-primary-900/10 shadow-md'
                  : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <code className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                  {exec.job_id?.slice(0, 8)}...
                </code>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[exec.status] || STATUS_STYLES.running}`}>
                  {STATUS_ICONS[exec.status]}
                  {exec.status}
                </span>
              </div>
              <div className="flex items-center gap-2 mb-1">
                {exec.agent_role && (
                  <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 capitalize">
                    {exec.agent_role}
                  </span>
                )}
                {exec.agent_mode && (
                  <span className="text-xs text-gray-400 dark:text-gray-500">{exec.agent_mode}</span>
                )}
              </div>
              {exec.step_name && (
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">step: {exec.step_name}</p>
              )}
              <div className="flex items-center justify-between mt-2 text-xs text-gray-400 dark:text-gray-500">
                <span className="flex items-center gap-1">
                  <Clock size={12} />
                  {exec.started_at ? new Date(exec.started_at).toLocaleTimeString() : '—'}
                </span>
                <span>{exec.event_count} events</span>
              </div>
            </button>
          ))}
        </div>

        {/* Event Detail Panel */}
        <div className="lg:col-span-2">
          {!selectedJobId ? (
            <div className="text-center py-24 text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
              <Search size={48} className="mx-auto mb-3 opacity-50" />
              <p>Select an execution to view events</p>
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              {/* Summary Bar */}
              {eventsData?.summary && (
                <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                  <div className="flex items-center justify-between mb-3">
                    <code className="text-sm font-mono text-gray-700 dark:text-gray-300">{selectedJobId}</code>
                    {eventsData.summary.duration_seconds != null && (
                      <span className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1">
                        <Clock size={14} />
                        {eventsData.summary.duration_seconds}s
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <StatBadge icon={<MessageSquare size={14} />} label="Text" value={eventsData.summary.text_events} color="blue" />
                    <StatBadge icon={<Wrench size={14} />} label="Tool calls" value={eventsData.summary.tool_use_events} color="amber" />
                    <StatBadge icon={<FileText size={14} />} label="Tool results" value={eventsData.summary.tool_result_events} color="green" />
                    <StatBadge icon={<AlertCircle size={14} />} label="Errors" value={eventsData.summary.error_events} color="red" />
                    {eventsData.summary.tools_used.length > 0 && (
                      <div className="flex items-center gap-1 ml-2">
                        <span className="text-xs text-gray-400">Tools:</span>
                        {eventsData.summary.tools_used.map(t => (
                          <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 font-mono">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Event Timeline */}
              <div className="divide-y divide-gray-100 dark:divide-gray-700/50 max-h-[60vh] overflow-y-auto">
                {(eventsData?.events || []).map((event, idx) => (
                  <EventRow key={idx} event={event} />
                ))}
                {eventsData?.events?.length === 0 && (
                  <div className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
                    No events in log file
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


function StatBadge({ icon, label, value, color }) {
  const colors = {
    blue: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
    amber: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
    green: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
    red: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
  }
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium ${colors[color]}`}>
      {icon}
      {label}: {value}
    </span>
  )
}


function EventRow({ event }) {
  const [expanded, setExpanded] = useState(false)
  const type = event.type || ''
  const subtype = event.subtype || ''
  const ts = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : ''

  let icon, label, borderColor, content
  if (type === 'text') {
    icon = <MessageSquare size={14} className="text-blue-500" />
    label = 'Text'
    borderColor = 'border-l-blue-500'
    content = event.text
  } else if (type === 'tool_use') {
    icon = <Wrench size={14} className="text-amber-500" />
    label = event.tool || 'Tool'
    borderColor = 'border-l-amber-500'
    content = event.input != null ? JSON.stringify(event.input, null, 2) : null
  } else if (type === 'tool_result') {
    icon = <FileText size={14} className="text-green-500" />
    label = 'Result'
    borderColor = 'border-l-green-500'
    content = typeof event.output === 'string' ? event.output : (event.output != null ? JSON.stringify(event.output, null, 2) : null)
  } else if (type === 'reasoning') {
    icon = <MessageSquare size={14} className="text-purple-500" />
    label = 'Reasoning'
    borderColor = 'border-l-purple-500'
    content = event.text
  } else if (type === 'system') {
    icon = <AlertCircle size={14} className="text-gray-400" />
    label = subtype || 'System'
    borderColor = 'border-l-gray-400'
    content = event.text || event.result || event.error
  } else if (type === 'result') {
    icon = event.error
      ? <XCircle size={14} className="text-red-500" />
      : <CheckCircle size={14} className="text-green-500" />
    label = event.error ? 'Error' : 'Result'
    borderColor = event.error ? 'border-l-red-500' : 'border-l-green-500'
    content = event.error || event.result
  } else {
    icon = <FileText size={14} className="text-gray-400" />
    label = type || 'Unknown'
    borderColor = 'border-l-gray-400'
    content = JSON.stringify(event, null, 2)
  }

  const hasContent = content && content.length > 0
  const isLong = hasContent && content.length > 200

  return (
    <div className={`px-4 py-3 border-l-4 ${borderColor} hover:bg-gray-50 dark:hover:bg-gray-700/30 transition`}>
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => isLong && setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">{label}</span>
          {event.tool_use_id && (
            <code className="text-[10px] text-gray-400 font-mono">{event.tool_use_id.slice(0, 8)}</code>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-400">{ts}</span>
          {isLong && (expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />)}
        </div>
      </div>
      {hasContent && (
        <pre className={`mt-2 text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap font-mono ${
          isLong && !expanded ? 'max-h-20 overflow-hidden' : 'max-h-96 overflow-y-auto'
        }`}>
          {content}
        </pre>
      )}
    </div>
  )
}
