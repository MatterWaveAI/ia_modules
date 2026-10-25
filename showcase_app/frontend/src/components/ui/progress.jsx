/**
 * Progress Component
 * Simple Tailwind implementation matching shadcn/ui API
 */

import React from 'react';

export function Progress({ value = 0, max = 100, className = '', ...props }) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div
      className={`
        relative h-4 w-full overflow-hidden rounded-full bg-gray-200
        ${className}
      `}
      {...props}
    >
      <div
        className="h-full bg-blue-600 transition-all duration-300 ease-in-out"
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}
