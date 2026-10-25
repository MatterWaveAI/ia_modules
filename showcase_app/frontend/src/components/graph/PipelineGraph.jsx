import React, { useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import 'reactflow/dist/style.css'

import StepNode from './StepNode'
import DecisionNode from './DecisionNode'
import ParallelNode from './ParallelNode'
import { generateGraph } from './graphGenerator'
import { useExecutionSync } from './hooks/useExecutionSync'

const nodeTypes = {
  step: StepNode,
  decision: DecisionNode,
  parallel: ParallelNode,
}

export default function PipelineGraph({ pipeline, execution }) {
  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    try {
      const graph = generateGraph(pipeline)
      console.log('Generated graph:', {
        nodes: graph.nodes.length,
        edges: graph.edges.length
      })
      return graph
    } catch (error) {
      console.error('Error generating graph:', error)
      return { nodes: [], edges: [] }
    }
  }, [pipeline])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  useExecutionSync(execution, setNodes)

  if (nodes.length === 0) {
    return (
      <div className="h-[600px] flex items-center justify-center bg-gray-50 dark:bg-gray-800/50 rounded-lg border dark:border-gray-700">
        <div className="text-gray-500">No pipeline graph available</div>
      </div>
    )
  }

  return (
    <div className="h-[600px] bg-gray-50 dark:bg-gray-800/50 rounded-lg border dark:border-gray-700">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={{
          type: 'smoothstep',
          style: { strokeWidth: 1.5 },
        }}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        attributionPosition="bottom-left"
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  )
}
