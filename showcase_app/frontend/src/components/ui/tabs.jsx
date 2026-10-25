/**
 * Tabs Component
 * Simple Tailwind implementation matching shadcn/ui API
 */

import React, { useState, createContext, useContext } from 'react';

const TabsContext = createContext();

export function Tabs({ defaultValue, value: controlledValue, onValueChange, className = '', children }) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const value = controlledValue !== undefined ? controlledValue : internalValue;

  const handleValueChange = (newValue) => {
    if (controlledValue === undefined) {
      setInternalValue(newValue);
    }
    if (onValueChange) {
      onValueChange(newValue);
    }
  };

  return (
    <TabsContext.Provider value={{ value, onValueChange: handleValueChange }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({ className = '', children }) {
  return (
    <div
      className={`
        inline-flex h-10 items-center justify-center rounded-md
        bg-gray-100 p-1 text-gray-500
        ${className}
      `}
    >
      {children}
    </div>
  );
}

export function TabsTrigger({ value, className = '', children }) {
  const context = useContext(TabsContext);
  const isActive = context.value === value;

  return (
    <button
      type="button"
      onClick={() => context.onValueChange(value)}
      className={`
        inline-flex items-center justify-center whitespace-nowrap rounded-sm
        px-3 py-1.5 text-sm font-medium ring-offset-white
        transition-all focus-visible:outline-none focus-visible:ring-2
        focus-visible:ring-blue-500 focus-visible:ring-offset-2
        disabled:pointer-events-none disabled:opacity-50
        ${
          isActive
            ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 shadow-sm'
            : 'text-gray-600 hover:bg-gray-200 hover:text-gray-900'
        }
        ${className}
      `}
    >
      {children}
    </button>
  );
}

export function TabsContent({ value, className = '', children }) {
  const context = useContext(TabsContext);
  if (context.value !== value) return null;

  return (
    <div
      className={`
        mt-2 ring-offset-white focus-visible:outline-none
        focus-visible:ring-2 focus-visible:ring-blue-500
        focus-visible:ring-offset-2
        ${className}
      `}
    >
      {children}
    </div>
  );
}
