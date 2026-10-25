import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { telemetryAPI } from '../services/api'
import { Users, MessageSquare, Zap, AlertCircle, FileText } from 'lucide-react'
import AgentPerformanceChart from '../components/charts/AgentPerformanceChart'
import MessageFlowChart from '../components/charts/MessageFlowChart'

export default function AgentDashboard() {
  const { data: agentData } = useQuery({
    queryKey: ['agent-metrics'],
    queryFn: async () => {
      const response = await telemetryAPI.getAgentMetrics()
      return response.data
    },
    refetchInterval: 10000,
  })

  const summary = agentData?.summary || {}
  const agents = agentData?.agents || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">Agent Dashboard</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Real-time agent execution and communication metrics</p>
        </div>
        <Link
          to="/agents/executions"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium transition"
        >
          <FileText size={16} />
          View Executions
        </Link>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Active Agents"
          value={summary.total_agents || 0}
          icon={<Users size={24} />}
          color="blue"
        />
        <SummaryCard
          label="Total Executions"
          value={summary.total_executions || 0}
          icon={<Zap size={24} />}
          color="green"
        />
        <SummaryCard
          label="Total Messages"
          value={summary.total_messages || 0}
          icon={<MessageSquare size={24} />}
          color="purple"
        />
        <SummaryCard
          label="Total Errors"
          value={summary.total_errors || 0}
          icon={<AlertCircle size={24} />}
          color="red"
        />
      </div>

      {/* Agent Performance Chart */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Agent Performance</h2>
        <AgentPerformanceChart agents={agents} />
      </div>

      {/* Message Flow */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Inter-Agent Message Flow</h2>
        <MessageFlowChart agents={agents} />
      </div>

      {/* Agent Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Agent Details</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Agent</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Role</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Executions</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Errors</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Msgs Sent</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Msgs Recv</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">State R/W</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {agents.map(agent => (
                <tr key={agent.name} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{agent.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">{agent.role}</td>
                  <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">{agent.executions}</td>
                  <td className="px-4 py-3 text-sm text-right text-red-600">{agent.errors}</td>
                  <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">{agent.messages_sent}</td>
                  <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">{agent.messages_received}</td>
                  <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">
                    {agent.state_reads}/{agent.state_writes}
                  </td>
                </tr>
              ))}
              {agents.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                    No agent data yet. Run multi-agent pipelines to see metrics here.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function SummaryCard({ label, value, icon, color }) {
  const colors = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    red: 'bg-red-100 text-red-600',
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className={`${colors[color]} rounded-lg p-2 w-fit mb-2`}>{icon}</div>
      <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">{value}</div>
      <div className="text-sm text-gray-600 dark:text-gray-400">{label}</div>
    </div>
  )
}
