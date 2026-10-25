import React from 'react'
import { cva } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const spinnerVariants = cva(
  'animate-spin rounded-full border-solid border-t-transparent',
  {
    variants: {
      size: {
        xs: 'h-3 w-3 border-2',
        sm: 'h-4 w-4 border-2',
        md: 'h-8 w-8 border-3',
        lg: 'h-12 w-12 border-4',
        xl: 'h-16 w-16 border-4',
      },
      variant: {
        primary: 'border-primary-600 dark:border-primary-400',
        secondary: 'border-gray-600 dark:border-gray-400',
        white: 'border-white',
        success: 'border-green-600 dark:border-green-400',
        danger: 'border-red-600 dark:border-red-400',
      },
    },
    defaultVariants: {
      size: 'md',
      variant: 'primary',
    },
  }
)

export const Spinner = ({ size, variant, className, ...props }) => {
  return (
    <div
      className={cn(spinnerVariants({ size, variant }), className)}
      role="status"
      aria-label="Loading"
      {...props}
    >
      <span className="sr-only">Loading...</span>
    </div>
  )
}

export const LoadingSpinner = ({ text = 'Loading...', size = 'md', variant = 'primary', className }) => {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-3', className)}>
      <Spinner size={size} variant={variant} />
      {text && <p className="text-sm text-gray-600 dark:text-gray-400">{text}</p>}
    </div>
  )
}

export const InlineSpinner = ({ text, size = 'sm', variant = 'primary', className }) => {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Spinner size={size} variant={variant} />
      {text && <span className="text-sm text-gray-600 dark:text-gray-400">{text}</span>}
    </div>
  )
}

export const ButtonSpinner = ({ size = 'xs', variant = 'white' }) => {
  return <Spinner size={size} variant={variant} />
}

export default Spinner
