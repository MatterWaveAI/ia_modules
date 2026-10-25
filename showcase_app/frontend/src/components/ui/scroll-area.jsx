/**
 * ScrollArea Component
 * Simple Tailwind implementation matching shadcn/ui API
 */

import React from 'react';

export function ScrollArea({ className = '', children, ...props }) {
  return (
    <div
      className={`
        relative overflow-auto
        scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100
        hover:scrollbar-thumb-gray-400
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
}
