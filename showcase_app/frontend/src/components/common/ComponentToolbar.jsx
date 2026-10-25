import React from 'react'
import { Save, RotateCcw, Plus } from 'lucide-react'

/**
 * ComponentToolbar - Toolbar for managing drag-drop components
 * Provides buttons for adding components, saving pipelines, and resetting layout
 */
export default function ComponentToolbar({
  availableComponents = [],
  onAddComponent,
  onSavePipeline,
  onResetLayout
}) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-md border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100">Customize Layout</h3>
        <div className="flex space-x-2">
          <button
            onClick={onSavePipeline}
            className="flex items-center px-3 py-1 bg-purple-100 dark:bg-purple-900/30 hover:bg-purple-200 dark:hover:bg-purple-800/40 text-purple-800 dark:text-purple-300 rounded text-sm transition-colors"
            title="Save current layout as a new pipeline"
          >
            <Save className="w-4 h-4 mr-1" />
            Save as Pipeline
          </button>
          <button
            onClick={onResetLayout}
            className="flex items-center px-3 py-1 bg-red-100 dark:bg-red-900/30 hover:bg-red-200 dark:hover:bg-red-800/40 text-red-800 dark:text-red-300 rounded text-sm transition-colors"
            title="Reset to default layout"
          >
            <RotateCcw className="w-4 h-4 mr-1" />
            Reset Layout
          </button>
        </div>
      </div>

      <div className="mb-2">
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Add Components:</h4>
        <div className="flex flex-wrap gap-2">
          {availableComponents.map(componentType => (
            <button
              key={componentType}
              onClick={() => onAddComponent(componentType)}
              className="flex items-center px-3 py-1 bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-800/40 text-blue-800 dark:text-blue-300 rounded text-sm transition-colors"
              title={`Add ${componentType} component`}
            >
              <Plus className="w-3 h-3 mr-1" />
              {componentType}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}