/**
 * Input Component
 * Simple Tailwind implementation matching shadcn/ui API
 */

import React from 'react';

export function Input({ className = '', type = 'text', ...props }) {
  return (
    <input
      type={type}
      className={`
        flex h-10 w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2
        text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2
        focus:ring-blue-500 focus:border-transparent disabled:cursor-not-allowed
        disabled:opacity-50
        ${className}
      `}
      {...props}
    />
  );
}
