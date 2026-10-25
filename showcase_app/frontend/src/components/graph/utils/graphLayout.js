/**
 * Calculate graph levels using BFS traversal
 */
export function calculateLevels(flow, steps) {
  const { outgoing } = buildAdjacencyList(flow.paths)
  const levels = {}
  const queue = [flow.start_at]
  levels[flow.start_at] = 0

  while (queue.length > 0) {
    const current = queue.shift()
    const currentLevel = levels[current]

    if (outgoing[current]) {
      outgoing[current].forEach(({ target }) => {
        if (levels[target] === undefined) {
          levels[target] = currentLevel + 1
          queue.push(target)
        } else {
          levels[target] = Math.max(levels[target], currentLevel + 1)
        }
      })
    }
  }

  return levels
}

/**
 * Build adjacency list from flow paths
 */
export function buildAdjacencyList(paths) {
  const outgoing = {}
  const incoming = {}

  paths.forEach(path => {
    const from = path.from_step
    const to = path.to_step

    if (!outgoing[from]) outgoing[from] = []
    if (!incoming[to]) incoming[to] = []

    outgoing[from].push({ target: to, path })
    incoming[to].push({ source: from, path })
  })

  return { outgoing, incoming }
}

/**
 * Group steps by their graph level
 */
export function groupByLevel(levels) {
  const stepsByLevel = {}

  Object.keys(levels).forEach(stepId => {
    const level = levels[stepId]
    if (!stepsByLevel[level]) stepsByLevel[level] = []
    stepsByLevel[level].push(stepId)
  })

  return stepsByLevel
}

/**
 * Calculate node position based on level and index
 */
export function calculateNodePosition(level, index, totalAtLevel, config = {}) {
  const {
    nodeWidth = 200,
    levelHeight = 150,
    canvasWidth = 800,
  } = config

  const totalWidth = totalAtLevel * nodeWidth
  const startX = (canvasWidth - totalWidth) / 2
  const x = startX + index * nodeWidth + nodeWidth / 2
  const y = level * levelHeight

  return { x, y }
}
