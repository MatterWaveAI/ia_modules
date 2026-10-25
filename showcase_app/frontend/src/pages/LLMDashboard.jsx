import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { telemetryAPI } from '../services/api'
import { Cpu, DollarSign, Zap } from 'lucide-react'
import LLMUsageChart from '../components/charts/LLMUsageChart'

export default function LLMDashboard() {
  const [chartView, setChartView] = useState('cost')

  const { data: llmData } = useQuery({
    queryKey: ['llm-metrics'],
    queryFn: async () => {
      const response = await telemetryAPI.getLLMUsage()
      return response.data
    },
    refetchInterval: 10000,
  })

  const summary = llmData?.summary || {}
  const models = llmData?.models || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">LLM Usage Dashboard</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">Token consumption, cost breakdown, and model performance</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="bg-blue-100 text-blue-600 rounded-lg p-2 w-fit mb-2">
            <Zap size={24} />
          </div>
          <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">{summary.total_requests || 0}</div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Total Requests</div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="bg-green-100 text-green-600 rounded-lg p-2 w-fit mb-2">
            <DollarSign size={24} />
          </div>
          <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">
            ${(summary.total_cost_usd || 0).toFixed(4)}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Total Cost</div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="bg-purple-100 text-purple-600 rounded-lg p-2 w-fit mb-2">
            <Cpu size={24} />
          </div>
          <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">{summary.model_count || 0}</div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Models Used</div>
        </div>
      </div>

      {/* Cost / Requests Chart */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Usage by Model</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setChartView('cost')}
              className={`px-3 py-1 rounded text-sm ${
                chartView === 'cost'
                  ? 'bg-blue-100 text-blue-700 font-medium'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
              }`}
            >
              Cost
            </button>
            <button
              onClick={() => setChartView('requests')}
              className={`px-3 py-1 rounded text-sm ${
                chartView === 'requests'
                  ? 'bg-blue-100 text-blue-700 font-medium'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
              }`}
            >
              Requests
            </button>
          </div>
        </div>
        <LLMUsageChart models={models} view={chartView} />
      </div>

      {/* Model Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Model Details</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Provider</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Model</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Requests</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Errors</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Cost (USD)</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {models.map((model, i) => (
                <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 capitalize">{model.system}</td>
                  <td className="px-4 py-3 text-sm font-mono text-gray-900 dark:text-gray-100">{model.model}</td>
                  <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">{model.requests}</td>
                  <td className="px-4 py-3 text-sm text-right text-red-600">{model.errors}</td>
                  <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">
                    ${model.total_cost_usd.toFixed(4)}
                  </td>
                </tr>
              ))}
              {models.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                    No LLM usage data yet. Run pipelines with LLM steps to see metrics here.
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
