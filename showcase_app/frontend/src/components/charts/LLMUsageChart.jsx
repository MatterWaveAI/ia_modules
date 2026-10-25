import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts'

const COLORS = ['#3b82f6', '#22c55e', '#f97316', '#a855f7', '#ef4444', '#06b6d4']

export default function LLMUsageChart({ models, view = 'cost' }) {
  if (!models || models.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        <p>No LLM usage data available.</p>
      </div>
    )
  }

  if (view === 'cost') {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={models}
            cx="50%"
            cy="50%"
            outerRadius={100}
            dataKey="total_cost_usd"
            nameKey="model"
            label={({ model, total_cost_usd }) => `${model}: $${total_cost_usd.toFixed(3)}`}
          >
            {models.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value) => `$${value.toFixed(4)}`} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={models}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="model" fontSize={11} angle={-20} textAnchor="end" height={60} />
        <YAxis />
        <Tooltip />
        <Legend />
        <Bar dataKey="requests" name="Requests" fill="#3b82f6" />
        <Bar dataKey="errors" name="Errors" fill="#ef4444" />
      </BarChart>
    </ResponsiveContainer>
  )
}
