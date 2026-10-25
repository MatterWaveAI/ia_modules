import React from 'react'
import { FileText, Download, Copy } from 'lucide-react'

/**
 * PipelineTemplateCard - Displays a single pipeline template with import/clone options
 */
export default function PipelineTemplateCard({ template, onImport, onClone }) {
  const stepCount = template.config?.steps?.length || 0
  const tags = template.metadata?.tags || []

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md transition-all duration-200 bg-white dark:bg-gray-900">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center">
          <FileText className="w-5 h-5 text-blue-600 mr-2 flex-shrink-0" />
          <div>
            <h3 className="font-semibold text-gray-800 dark:text-gray-100 text-sm">{template.name}</h3>
            <p className="text-xs text-gray-500 mt-1">
              {stepCount} step{stepCount !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        <div className="flex space-x-1">
          <button
            onClick={() => onImport(template)}
            className="p-1.5 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
            title="Import into drag-drop editor"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={() => onClone(template)}
            className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/30 rounded transition-colors"
            title="Create new pipeline from template"
          >
            <Copy className="w-4 h-4" />
          </button>
        </div>
      </div>

      <p className="text-xs text-gray-600 dark:text-gray-400 mb-3 line-clamp-2">
        {template.description}
      </p>

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tags.slice(0, 3).map(tag => (
            <span
              key={tag}
              className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded text-xs"
            >
              {tag}
            </span>
          ))}
          {tags.length > 3 && (
            <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 rounded text-xs">
              +{tags.length - 3}
            </span>
          )}
        </div>
      )}
    </div>
  )
}