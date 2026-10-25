import { useEffect } from 'react'

/**
 * Sync execution status with graph nodes
 */
export function useExecutionSync(execution, setNodes) {
  useEffect(() => {
    if (!execution?.steps || !Array.isArray(execution.steps)) return

    setNodes((nodes) =>
      nodes.map((node) => {
        const step = findMatchingStep(execution.steps, node.id)

        if (step) {
          return {
            ...node,
            data: {
              ...node.data,
              status: step.status,
              duration: step.duration_ms,
            },
          }
        }

        return node
      })
    )
  }, [execution?.steps, setNodes])
}

/**
 * Find step that matches node ID
 */
function findMatchingStep(steps, nodeId) {
  // Safety check - ensure steps is an array
  if (!Array.isArray(steps)) return null
  
  return steps.find((step) => {
    // Match by step_name containing node ID
    if (step.step_name && step.step_name.includes(nodeId)) return true

    // Match by node ID containing step name
    if (nodeId.includes(step.step_name)) return true

    // Match by step_index
    const nodeIndex = parseInt(nodeId.replace(/\D/g, ''))
    if (!isNaN(nodeIndex) && step.step_index === nodeIndex - 1) return true

    return false
  })
}
