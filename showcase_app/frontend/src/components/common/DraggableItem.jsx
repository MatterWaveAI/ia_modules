import React from 'react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, X } from 'lucide-react'

/**
 * DraggableItem - A reusable draggable wrapper component
 * Provides drag handle, remove button, and proper styling
 */
export default function DraggableItem({ id, children, onRemove, className = "" }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`relative group bg-white dark:bg-gray-900 rounded-lg shadow-md border border-gray-200 dark:border-gray-700 mb-4 ${className}`}
    >
      {/* Drag handle and remove button header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 rounded-t-lg">
        <div
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
          title="Drag to reorder"
        >
          <GripVertical className="w-4 h-4 text-gray-500" />
        </div>
        {onRemove && (
          <button
            onClick={() => onRemove(id)}
            className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
            title="Remove component"
          >
            <X className="w-4 h-4 text-red-500" />
          </button>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        {children}
      </div>
    </div>
  )
}