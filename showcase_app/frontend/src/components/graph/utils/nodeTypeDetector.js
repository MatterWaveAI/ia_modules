/**
 * Determine node type based on outgoing/incoming edges
 */
export function detectNodeType(stepId, outgoing, incoming) {
  const outCount = outgoing[stepId]?.length || 0
  const inCount = incoming[stepId]?.length || 0

  // Check if this is a conditional split point
  const hasConditionalOut = outgoing[stepId]?.some(({ path }) =>
    path.condition && path.condition.type !== 'always'
  )

  if (hasConditionalOut && outCount > 1) {
    return 'decision'
  }

  if (outCount > 2 || inCount > 2) {
    return 'parallel'
  }

  return 'step'
}
