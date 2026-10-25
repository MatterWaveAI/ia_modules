import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell
} from 'recharts'

const COLORS = ['#3b82f6', '#22c55e', '#f97316', '#a855f7', '#ef4444', '#06b6d4', '#eab308']

export default function PipelineBreakdownChart({ steps }) {
  if (!steps || steps.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        <p>No pipeline step data available.</p>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={steps}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" fontSize={12} />
        <YAxis label={{ value: 'Duration (ms)', angle: -90, position: 'insideLeft' }} />
        <Tooltip formatter={(value) => `${value.toFixed(1)}ms`} />
        <Bar dataKey="duration_ms" name="Duration">
          {steps.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
