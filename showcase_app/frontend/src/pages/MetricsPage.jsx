import React, { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { metricsAPI } from '../services/api'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Activity, CheckCircle, AlertCircle, Users, Zap, Clock } from 'lucide-react'
import { useMetricsWebSocket } from '../hooks/useWebSocket'
import MetricsTrendChart from '../components/charts/MetricsTrendChart'

export default function MetricsPage() {
  const queryClient = useQueryClient()

  const { data: report } = useQuery({
    queryKey: ['metrics-report'],
    queryFn: async () => {
      const response = await metricsAPI.getReport()
      return response.data
    },
    refetchInterval: false, // Disabled - using WebSocket instead
  })

  const { data: slo } = useQuery({
    queryKey: ['metrics-slo'],
    queryFn: async () => {
      const response = await metricsAPI.getSLO()
      return response.data
    },
    refetchInterval: false, // Disabled - using WebSocket instead
  })

  // Use WebSocket for real-time updates
  const handleWebSocketUpdate = useCallback((data) => {
    // Invalidate metrics queries when updates come in
    queryClient.invalidateQueries(['metrics-report'])
    queryClient.invalidateQueries(['metrics-slo'])
  }, [queryClient])

  const { isConnected } = useMetricsWebSocket(handleWebSocketUpdate)

  const { data: timeseries } = useQuery({
    queryKey: ['metrics-timeseries'],
    queryFn: async () => {
      const response = await metricsAPI.getHistory(24)
      return response.data?.datapoints || []
    },
    refetchInterval: 30000,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Reliability Metrics</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">Real-time EARF compliance monitoring and analytics</p>
      </div>

      {/* Core Metrics */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Core EARF Metrics</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <MetricCard
            label="SVR - Step Validity Rate"
            value={`${((report?.svr || 0) * 100).toFixed(1)}%`}
            icon={<CheckCircle size={24} />}
            color="green"
            target={slo?.svr_target ? `Target: >${(slo.svr_target * 100).toFixed(0)}%` : null}
            compliant={slo?.svr_compliant}
          />
          <MetricCard
            label="CR - Compensation Rate"
            value={`${((report?.cr || 0) * 100).toFixed(1)}%`}
            icon={<AlertCircle size={24} />}
            color="yellow"
            target={slo?.cr_target ? `Target: <${(slo.cr_target * 100).toFixed(0)}%` : null}
            compliant={slo?.cr_compliant}
          />
          <MetricCard
            label="PC - Plan Churn"
            value={report?.pc !== undefined ? report.pc.toFixed(2) : 'N/A'}
            icon={<Activity size={24} />}
            color="blue"
          />
          <MetricCard
            label="HIR - Human Intervention Rate"
            value={`${((report?.hir || 0) * 100).toFixed(1)}%`}
            icon={<Users size={24} />}
            color="purple"
            target={slo?.hir_target ? `Target: <${(slo.hir_target * 100).toFixed(0)}%` : null}
            compliant={slo?.hir_compliant}
          />
          <MetricCard
            label="MA - Model Accuracy"
            value={report?.ma ? `${(report.ma * 100).toFixed(1)}%` : 'N/A'}
            icon={<CheckCircle size={24} />}
            color="green"
            target={slo?.ma_target ? `Target: >${(slo.ma_target * 100).toFixed(0)}%` : null}
            compliant={slo?.ma_compliant}
          />
          <MetricCard
            label="TCL - Tool Call Latency"
            value={report?.tcl ? `${report.tcl.toFixed(0)}ms` : 'N/A'}
            icon={<Zap size={24} />}
            color="orange"
          />
        </div>
      </div>

      {/* Extended Metrics */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Extended Reliability Metrics</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <MetricCard
            label="MTTE - Mean Time to Error"
            value={report?.mtte ? `${report.mtte.toFixed(1)}h` : 'N/A'}
            icon={<Clock size={24} />}
            color="indigo"
          />
          <MetricCard
            label="RSR - Retry Success Rate"
            value={report?.rsr ? `${(report.rsr * 100).toFixed(1)}%` : 'N/A'}
            icon={<Activity size={24} />}
            color="blue"
          />
          <MetricCard
            label="EQS - Explanation Quality Score"
            value={report?.eqs ? `${(report.eqs * 100).toFixed(1)}%` : 'N/A'}
            icon={<CheckCircle size={24} />}
            color="green"
          />
          <MetricCard
            label="WCT - Workflow Completion Time"
            value={report?.wct ? `${report.wct.toFixed(0)}ms` : 'N/A'}
            icon={<Clock size={24} />}
            color="orange"
          />
          <MetricCard
            label="TPW - Tokens Per Workflow"
            value={report?.tpw ? report.tpw.toFixed(0) : 'N/A'}
            icon={<Activity size={24} />}
            color="purple"
          />
          <MetricCard
            label="CPSW - Cost Per Successful Workflow"
            value={report?.cpsw ? `$${report.cpsw.toFixed(3)}` : 'N/A'}
            icon={<Activity size={24} />}
            color="indigo"
          />
        </div>
      </div>

      {/* SLO Compliance */}
      {slo && (
        <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">SLO Compliance Status</h2>
          <div className="space-y-3">
            <SLOStatus
              metric="Step Validity Rate (SVR)"
              current={slo.svr_current}
              target={slo.svr_target}
              compliant={slo.svr_compliant}
            />
            <SLOStatus
              metric="Compensation Rate (CR)"
              current={slo.cr_current}
              target={slo.cr_target}
              compliant={slo.cr_compliant}
              inverse
            />
            <SLOStatus
              metric="Human Intervention Rate (HIR)"
              current={slo.hir_current}
              target={slo.hir_target}
              compliant={slo.hir_compliant}
              inverse
            />
            <SLOStatus
              metric="Model Accuracy (MA)"
              current={slo.ma_current}
              target={slo.ma_target}
              compliant={slo.ma_compliant}
            />
          </div>

          <div className="mt-4 p-4 rounded-lg bg-gray-50 dark:bg-gray-800/50">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-gray-800 dark:text-gray-100">Overall Compliance</span>
              <span
                className={`px-3 py-1 rounded-full text-sm font-medium ${
                  slo.overall_compliant
                    ? 'bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300'
                    : 'bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300'
                }`}
              >
                {slo.overall_compliant ? 'Compliant' : 'Non-Compliant'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Workflow Statistics */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Workflow Statistics</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatRow label="Total Workflows" value={report?.total_workflows || 0} />
          <StatRow label="Total Steps" value={report?.total_steps || 0} />
          <StatRow label="Avg Steps/Workflow" value={report?.total_workflows > 0 ? (report.total_steps / report.total_workflows).toFixed(1) : '0'} />
          <StatRow label="Success Rate" value={`${((report?.svr || 0) * 100).toFixed(1)}%`} color="green" />
        </div>
      </div>

      {/* EARF Three Pillars */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">EARF Three Pillars</h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Enterprise Agent Reliability Framework - Production-ready AI agent development
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <EARFPillar
            title="Total Observability"
            description="Complete visibility into agent behavior, decisions, and performance"
            features={[
              'Step-by-step execution tracking',
              'Comprehensive reliability metrics',
              'Real-time performance monitoring',
              'SLO compliance tracking',
              'Event history and audit logs'
            ]}
            metrics={[
              { label: 'SVR', value: report?.svr, format: 'percent' },
              { label: 'TCL', value: report?.tcl, format: 'ms' },
              { label: 'WCT', value: report?.wct, format: 'ms' }
            ]}
            color="blue"
          />
          <EARFPillar
            title="Absolute Reproducibility"
            description="Guaranteed deterministic behavior for debugging and compliance"
            features={[
              'Deterministic execution paths',
              'Complete state checkpointing',
              'Resume from any point',
              'Input/output data capture',
              'Execution replay capability'
            ]}
            metrics={[
              { label: 'CR', value: report?.cr, format: 'percent' },
              { label: 'PC', value: report?.pc, format: 'number' },
              { label: 'RSR', value: report?.rsr, format: 'percent' }
            ]}
            color="green"
          />
          <EARFPillar
            title="Formal Safety & Verification"
            description="Built-in safety controls, validation, and human oversight"
            features={[
              'Human-in-the-loop workflows',
              'Schema validation',
              'Safety constraints',
              'Approval gates',
              'Error compensation'
            ]}
            metrics={[
              { label: 'HIR', value: report?.hir, format: 'percent' },
              { label: 'MA', value: report?.ma, format: 'percent' },
              { label: 'EQS', value: report?.eqs, format: 'percent' }
            ]}
            color="purple"
          />
        </div>
      </div>

      {/* Metrics Trend Chart */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Metrics Trend (24h)</h2>
        <MetricsTrendChart data={timeseries} metrics={['svr', 'cr', 'hir', 'ma']} />
      </div>
    </div>
  )
}

function EARFPillar({ title, description, features, metrics, color }) {
  const colors = {
    blue: 'border-blue-500 bg-blue-50 dark:bg-blue-950/30',
    green: 'border-green-500 bg-green-50 dark:bg-green-950/30',
    purple: 'border-purple-500 bg-purple-50 dark:bg-purple-950/30',
  }

  const badgeColors = {
    blue: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300',
    green: 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300',
    purple: 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300',
  }

  const formatValue = (value, format) => {
    if (value === null || value === undefined) return 'N/A'
    if (format === 'percent') return `${(value * 100).toFixed(1)}%`
    if (format === 'ms') return `${value.toFixed(0)}ms`
    if (format === 'number') return value.toFixed(2)
    return value
  }

  return (
    <div className={`border-l-4 ${colors[color]} p-4 rounded-lg`}>
      <h3 className="text-lg font-bold text-gray-800 dark:text-gray-100 mb-2">{title}</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{description}</p>

      <div className="mb-4">
        <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Key Features:</p>
        <ul className="space-y-1">
          {features.map((feature, index) => (
            <li key={index} className="text-xs text-gray-600 dark:text-gray-400 flex items-start">
              <span className="mr-1">•</span>
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
        <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Metrics:</p>
        <div className="flex flex-wrap gap-2">
          {metrics.map((metric, index) => (
            <span key={index} className={`px-2 py-1 rounded text-xs font-medium ${badgeColors[color]}`}>
              {metric.label}: {formatValue(metric.value, metric.format)}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, icon, color, target, compliant }) {
  const colors = {
    green: 'bg-green-100 dark:bg-green-900/50 text-green-600 dark:text-green-400',
    yellow: 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-600 dark:text-yellow-400',
    blue: 'bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400',
    purple: 'bg-purple-100 dark:bg-purple-900/50 text-purple-600 dark:text-purple-400',
    orange: 'bg-orange-100 dark:bg-orange-900/50 text-orange-600 dark:text-orange-400',
    indigo: 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-400',
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-4 relative">
      {compliant !== undefined && (
        <div className={`absolute top-2 right-2 w-2 h-2 rounded-full ${compliant ? 'bg-green-500' : 'bg-red-500'}`}></div>
      )}
      <div className={`${colors[color]} rounded-lg p-2 w-fit mb-2`}>{icon}</div>
      <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">{value}</div>
      <div className="text-sm text-gray-600 dark:text-gray-400">{label}</div>
      {target && <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{target}</div>}
    </div>
  )
}

function SLOStatus({ metric, current, target, compliant, inverse = false }) {
  const percentage = (current / target) * 100
  const isGood = inverse ? current <= target : current >= target

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{metric}</span>
        <span className="text-sm text-gray-600 dark:text-gray-400">
          {(current * 100).toFixed(1)}% / {(target * 100).toFixed(1)}%
        </span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${isGood ? 'bg-green-500' : 'bg-red-500'}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        ></div>
      </div>
    </div>
  )
}

function StatRow({ label, value, color }) {
  const colors = {
    green: 'text-green-600 dark:text-green-400',
    red: 'text-red-600 dark:text-red-400',
  }

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
      <span className="text-gray-600 dark:text-gray-400">{label}</span>
      <span className={`font-semibold ${colors[color] || 'text-gray-800 dark:text-gray-100'}`}>{value}</span>
    </div>
  )
}
