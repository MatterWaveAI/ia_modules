import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'

export default function AgentPerformanceChart({ agents }) {
  if (!agents || agents.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        <p>No agent data available.</p>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={agents} layout="vertical" margin={{ left: 80 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" />
        <YAxis type="category" dataKey="name" fontSize={12} />
        <Tooltip />
        <Legend />
        <Bar dataKey="executions" name="Executions" fill="#3b82f6" />
        <Bar dataKey="errors" name="Errors" fill="#ef4444" />
        <Bar dataKey="messages_sent" name="Messages Sent" fill="#22c55e" />
      </BarChart>
    </ResponsiveContainer>
  )
}
