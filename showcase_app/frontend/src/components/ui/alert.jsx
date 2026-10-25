/**
 * Alert Component
 * Simple Tailwind implementation matching shadcn/ui API
 */

import React from 'react';

const variants = {
  default: 'bg-blue-50 text-blue-900 border-blue-200',
  destructive: 'bg-red-50 text-red-900 border-red-200',
};

export function Alert({ className = '', variant = 'default', children, ...props }) {
  return (
    <div
      className={`
        relative w-full rounded-lg border p-4
        ${variants[variant]}
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
}

export function AlertDescription({ className = '', children, ...props }) {
  return (
    <div
      className={`text-sm ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
