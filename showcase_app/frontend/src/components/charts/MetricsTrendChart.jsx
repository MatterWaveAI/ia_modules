import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const METRIC_COLORS = {
  svr: '#22c55e',
  cr: '#eab308',
  hir: '#a855f7',
  ma: '#3b82f6',
  tcl: '#f97316',
  wct: '#6366f1',
}

export default function MetricsTrendChart({ data, metrics = ['svr', 'cr', 'hir'] }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        <p>No time-series data available yet. Run pipelines to generate data.</p>
      </div>
    )
  }

  const formatted = data.map(point => ({
    ...point,
    time: new Date(point.timestamp * 1000).toLocaleTimeString(),
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={formatted}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time" fontSize={12} />
        <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
        <Tooltip
          formatter={(value, name) => [`${(value * 100).toFixed(1)}%`, name.toUpperCase()]}
          labelFormatter={(label) => `Time: ${label}`}
        />
        <Legend />
        {metrics.map(metric => (
          <Line
            key={metric}
            type="monotone"
            dataKey={metric}
            stroke={METRIC_COLORS[metric] || '#8884d8'}
            strokeWidth={2}
            dot={false}
            name={metric.toUpperCase()}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
