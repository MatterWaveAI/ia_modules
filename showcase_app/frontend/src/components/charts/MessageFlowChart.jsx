import React, { useMemo } from 'react'
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow'
import 'reactflow/dist/style.css'

export default function MessageFlowChart({ agents }) {
  if (!agents || agents.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        <p>No message flow data available.</p>
      </div>
    )
  }

  const { nodes, edges } = useMemo(() => {
    const agentNodes = agents.map((agent, i) => ({
      id: agent.name,
      data: {
        label: (
          <div className="text-center">
            <div className="font-semibold">{agent.name}</div>
            <div className="text-xs text-gray-500">{agent.role}</div>
            <div className="text-xs mt-1">
              {agent.executions} runs | {agent.messages_sent} msgs
            </div>
          </div>
        )
      },
      position: {
        x: 150 + (i % 3) * 250,
        y: 50 + Math.floor(i / 3) * 150
      },
      style: {
        border: agent.errors > 0 ? '2px solid #ef4444' : '2px solid #3b82f6',
        borderRadius: '8px',
        padding: '10px',
        background: '#fff',
      }
    }))

    const agentEdges = []
    agents.forEach(agent => {
      if (agent.messages_sent > 0) {
        agents.forEach(target => {
          if (target.name !== agent.name && target.messages_received > 0) {
            agentEdges.push({
              id: `${agent.name}-${target.name}`,
              source: agent.name,
              target: target.name,
              label: `${agent.messages_sent}`,
              markerEnd: { type: MarkerType.ArrowClosed },
              style: { stroke: '#94a3b8' },
              labelStyle: { fontSize: 10 }
            })
          }
        })
      }
    })

    return { nodes: agentNodes, edges: agentEdges }
  }, [agents])

  return (
    <div style={{ height: 400 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        attributionPosition="bottom-left"
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  )
}
