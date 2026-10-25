import React, { useState } from 'react'
import { ChevronDown, ChevronRight, Braces } from 'lucide-react'
import ReactJson from '@microlink/react-json-view'

// Render a primitive value inline with a type-appropriate style.
function PrimitiveValue({ value }) {
  if (value === null) return <span className="text-gray-400 italic">null</span>
  if (value === undefined) return <span className="text-gray-400 italic">undefined</span>
  if (typeof value === 'boolean') {
    return <span className="text-purple-600 dark:text-purple-400 font-mono">{String(value)}</span>
  }
  if (typeof value === 'number') {
    return <span className="text-blue-600 dark:text-blue-400 font-mono">{value}</span>
  }
  if (typeof value === 'string') {
    const truncated = value.length > 120 ? `${value.slice(0, 120)}…` : value
    return <span className="text-green-700 dark:text-green-400 font-mono">"{truncated}"</span>
  }
  return null
}

// Non-primitive summary: object → "(N keys)", array → "(N items)".
function nonPrimitiveSummary(value) {
  if (Array.isArray(value)) return `[${value.length} item${value.length === 1 ? '' : 's'}]`
  if (value && typeof value === 'object') {
    const n = Object.keys(value).length
    return `{${n} key${n === 1 ? '' : 's'}}`
  }
  return ''
}

function SummaryRow({ entries }) {
  if (!entries.length) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400 italic">
        (empty)
      </div>
    )
  }
  return (
    <dl className="divide-y divide-gray-100 dark:divide-gray-800">
      {entries.map(([key, value]) => {
        const isPrimitive = value === null || typeof value !== 'object'
        return (
          <div key={key} className="flex items-start gap-4 py-2 text-sm">
            <dt className="w-40 flex-shrink-0 font-medium text-gray-700 dark:text-gray-300 truncate">
              {key}
            </dt>
            <dd className="flex-1 min-w-0 text-gray-900 dark:text-gray-200 break-words">
              {isPrimitive ? (
                <PrimitiveValue value={value} />
              ) : (
                <span className="text-gray-500 dark:text-gray-400 font-mono text-xs">
                  {nonPrimitiveSummary(value)}
                </span>
              )}
            </dd>
          </div>
        )
      })}
    </dl>
  )
}

function topLevelEntries(data) {
  if (Array.isArray(data)) return data.map((v, i) => [String(i), v])
  if (data && typeof data === 'object') return Object.entries(data)
  return [['value', data]]
}

export default function DataViewer({ title, data }) {
  const [jsonOpen, setJsonOpen] = useState(false)
  if (!data) return null

  const entries = topLevelEntries(data)

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100">{title}</h3>
      </div>

      {/* Summary: top-level keys + primitive values or type hint */}
      <div className="px-6 py-4">
        <SummaryRow entries={entries} />
      </div>

      {/* Fat accordion — raw JSON lives here, collapsed by default */}
      <div className="border-t border-gray-200 dark:border-gray-800">
        <button
          onClick={() => setJsonOpen(!jsonOpen)}
          className="w-full px-6 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors text-left"
        >
          <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            <Braces className="w-4 h-4" />
            Raw JSON
          </div>
          {jsonOpen ? (
            <ChevronDown className="w-5 h-5 text-gray-500 dark:text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-500 dark:text-gray-400" />
          )}
        </button>
        {jsonOpen && (
          <div className="px-6 pb-6 overflow-auto max-h-[600px]">
            <ReactJson
              src={data}
              theme="rjv-default"
              collapsed={1}
              displayDataTypes={false}
              enableClipboard={true}
              displayObjectSize={true}
              name={null}
            />
          </div>
        )}
      </div>
    </div>
  )
}
