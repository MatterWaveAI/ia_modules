/**
 * Label Component
 * Simple Tailwind implementation matching shadcn/ui API
 */

import React from 'react';

export function Label({ className = '', children, ...props }) {
  return (
    <label
      className={`
        text-sm font-medium text-gray-700 leading-none
        peer-disabled:cursor-not-allowed peer-disabled:opacity-70
        ${className}
      `}
      {...props}
    >
      {children}
    </label>
  );
}
