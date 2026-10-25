import React from 'react'
import { cn } from '../../lib/utils'
import { Button } from './button'

export const EmptyState = ({
  icon: Icon,
  title,
  description,
  action,
  actionLabel,
  className,
}) => {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center p-12 text-center',
      'rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-700',
      'bg-gray-50 dark:bg-gray-900/50',
      className
    )}>
      {Icon && (
        <div className="mb-4 rounded-full bg-gray-100 dark:bg-gray-800 p-6">
          <Icon className="h-12 w-12 text-gray-400 dark:text-gray-600" />
        </div>
      )}
      {title && (
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          {title}
        </h3>
      )}
      {description && (
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 max-w-md">
          {description}
        </p>
      )}
      {action && actionLabel && (
        <Button onClick={action}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}

export default EmptyState
