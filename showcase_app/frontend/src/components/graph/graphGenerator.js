import { calculateLevels, buildAdjacencyList, groupByLevel, calculateNodePosition } from './utils/graphLayout'
import { detectNodeType } from './utils/nodeTypeDetector'
import { formatEdge } from './utils/edgeFormatter'

/**
 * Generate graph nodes and edges from pipeline configuration
 * Supports both 'paths' and 'transitions' flow formats
 */
export function generateGraph(pipeline) {
  const config = pipeline.config
  const steps = config.steps || []
  const flow = config.flow || {}

  // Normalize flow format (handle both 'paths' and 'transitions')
  const paths = normalizePaths(flow)

  if (paths.length === 0) {
    return generateSequentialGraph(steps)
  }

  return generateFlowGraph(steps, { ...flow, paths })
}

/**
 * Normalize different flow path formats
 * Handles both from_step/to_step and from/to conventions
 */
function normalizePaths(flow) {
  const rawPaths = flow.paths || flow.transitions || []

  return rawPaths.map(p => ({
    from_step: p.from_step || p.from,
    to_step: p.to_step || p.to,
    condition: p.condition,
  }))
}

/**
 * Generate sequential graph (fallback when no flow defined)
 */
function generateSequentialGraph(steps) {
  const nodes = steps.map((step, idx) => ({
    id: step.id || `step${idx + 1}`,
    type: 'step',
    position: { x: 250, y: idx * 120 },
    data: { label: step.name, status: 'pending' },
  }))

  const edges = []
  for (let i = 0; i < steps.length - 1; i++) {
    edges.push({
      id: `e${i}-${i + 1}`,
      source: nodes[i].id,
      target: nodes[i + 1].id,
      type: 'smoothstep',
      animated: true,
    })
  }

  return { nodes, edges }
}

/**
 * Generate graph from flow definition
 */
function generateFlowGraph(steps, flow) {
  const stepMap = createStepMap(steps)
  const { outgoing, incoming } = buildAdjacencyList(flow.paths)
  const levels = calculateLevels(flow, steps)
  const stepsByLevel = groupByLevel(levels)

  const nodes = generateNodes(stepsByLevel, stepMap, outgoing, incoming)
  const edges = generateEdges(flow.paths, levels)

  return { nodes, edges }
}

/**
 * Create step ID to step object lookup map
 */
function createStepMap(steps) {
  const map = {}
  steps.forEach(step => {
    map[step.id] = step
  })
  return map
}

/**
 * Generate nodes from grouped steps
 */
function generateNodes(stepsByLevel, stepMap, outgoing, incoming) {
  const nodes = []

  Object.keys(stepsByLevel).forEach(level => {
    const stepsAtLevel = stepsByLevel[level]
    const levelNum = parseInt(level)

    stepsAtLevel.forEach((stepId, idx) => {
      const step = stepMap[stepId]
      if (!step) return

      const position = calculateNodePosition(
        levelNum,
        idx,
        stepsAtLevel.length
      )

      const nodeType = detectNodeType(stepId, outgoing, incoming)

      nodes.push({
        id: stepId,
        type: nodeType,
        position,
        data: {
          label: step.name,
          status: 'pending',
        },
      })
    })
  })

  return nodes
}

/**
 * Generate edges from flow paths
 * Detects back-edges (loops) where target level <= source level
 */
function generateEdges(paths, levels) {
  return paths.map(path => {
    const edgeId = `e-${path.from_step}-${path.to_step}`
    const sourceLevel = levels[path.from_step] ?? 0
    const targetLevel = levels[path.to_step] ?? 0
    const isBackEdge = targetLevel <= sourceLevel && path.from_step !== path.to_step

    const { label, style } = formatEdge(path, isBackEdge)

    return {
      id: edgeId,
      source: path.from_step,
      target: path.to_step,
      type: 'smoothstep',
      label,
      style,
      animated: !isBackEdge,
      labelStyle: { fontSize: 11, fontWeight: 500, fill: '#6b7280' },
      labelBgStyle: { fill: '#f9fafb', fillOpacity: 0.9 },
      labelBgPadding: [6, 3],
      labelBgBorderRadius: 4,
    }
  })
}
