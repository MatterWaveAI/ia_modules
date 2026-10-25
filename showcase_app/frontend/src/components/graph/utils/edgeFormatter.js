/**
 * Format operator symbols for display
 */
function formatOperator(operator) {
  const opMap = {
    equals: '=',
    not_equals: '≠',
    greater_than: '>',
    less_than: '<',
    gte: '≥',
    lte: '≤',
    '>=': '≥',
    '<=': '≤',
    '>': '>',
    '<': '<',
    '==': '=',
    '!=': '≠',
  }
  return opMap[operator] || operator
}

/**
 * Shorten a dotted source path for display
 * e.g. "review_content.approved" → "approved"
 * e.g. "result.requires_human_review" → "requires_human_review"
 */
function shortenSource(source) {
  if (!source) return ''
  const parts = source.split('.')
  return parts.length > 1 ? parts.slice(1).join('.') : source
}

/**
 * Format edge with appropriate label and style based on condition
 */
export function formatEdge(path, isBackEdge = false) {
  let label = undefined
  let style = {}

  const condition = path.condition

  if (condition && condition.type !== 'always') {
    switch (condition.type) {
      case 'threshold_condition': {
        const config = condition.config
        const field = config?.field || 'value'
        const operator = formatOperator(config?.operator || '')
        const value = config?.value ?? ''
        label = `${field} ${operator} ${value}`
        // Color-code threshold directions
        if (config?.operator === '>=' || config?.operator === '>') {
          style = { stroke: '#10b981', strokeWidth: 2 }
        } else if (config?.operator === '<' || config?.operator === '<=') {
          style = { stroke: '#ef4444', strokeWidth: 2 }
        }
        break
      }

      case 'expression': {
        const config = condition.config
        const source = shortenSource(config?.source)
        const operator = formatOperator(config?.operator || '')
        const value = config?.value ?? ''
        label = `${source} ${operator} ${value}`
        break
      }

      case 'field_equals': {
        const field = condition.field || ''
        const value = condition.value ?? ''
        label = `${field} = ${value}`
        break
      }

      case 'condition': {
        label = condition.description || 'if true'
        style = { stroke: '#3b82f6', strokeWidth: 2 }
        break
      }

      case 'else': {
        label = condition.description || 'else'
        style = { stroke: '#8b5cf6', strokeWidth: 2 }
        break
      }

      default:
        label = condition.description || condition.type
    }
  }

  // Style back-edges (loops) distinctly
  if (isBackEdge) {
    style = {
      ...style,
      strokeDasharray: '6 3',
      stroke: style.stroke || '#f59e0b',
      strokeWidth: style.strokeWidth || 2,
    }
    label = label ? `↺ ${label}` : '↺ loop'
  }

  return { label, style }
}
