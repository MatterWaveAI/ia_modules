/**
 * Select Component
 * Simple Tailwind implementation matching shadcn/ui API
 */

import React, { useState, useRef, useEffect } from 'react';

export function Select({ value, onValueChange, children }) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedValue, setSelectedValue] = useState(value);
  const ref = useRef(null);

  useEffect(() => {
    setSelectedValue(value);
  }, [value]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (ref.current && !ref.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      {React.Children.map(children, (child) => {
        if (child.type === SelectTrigger) {
          return React.cloneElement(child, { onClick: () => setIsOpen(!isOpen), selectedValue, isOpen });
        }
        if (child.type === SelectContent && isOpen) {
          return React.cloneElement(child, {
            onSelect: (val) => {
              setSelectedValue(val);
              onValueChange(val);
              setIsOpen(false);
            },
            selectedValue,
          });
        }
        return null;
      })}
    </div>
  );
}

export function SelectTrigger({ className = '', onClick, selectedValue, isOpen, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        flex h-10 w-full items-center justify-between rounded-md border
        border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm
        focus:outline-none focus:ring-2 focus:ring-blue-500
        disabled:cursor-not-allowed disabled:opacity-50
        ${className}
      `}
    >
      {children}
      <svg
        className={`h-4 w-4 opacity-50 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    </button>
  );
}

export function SelectValue({ placeholder }) {
  return <span className="text-gray-700 dark:text-gray-300">{placeholder}</span>;
}

export function SelectContent({ className = '', onSelect, selectedValue, children }) {
  return (
    <div
      className={`
        absolute z-50 mt-1 w-full rounded-md border border-gray-200 dark:border-gray-800
        bg-white dark:bg-gray-900 shadow-lg max-h-60 overflow-auto
        ${className}
      `}
    >
      <div className="py-1">
        {React.Children.map(children, (child) =>
          React.cloneElement(child, { onSelect, selectedValue })
        )}
      </div>
    </div>
  );
}

export function SelectItem({ value, onSelect, selectedValue, children }) {
  const isSelected = value === selectedValue;
  return (
    <div
      onClick={() => onSelect(value)}
      className={`
        relative flex cursor-pointer select-none items-center px-3 py-2
        text-sm hover:bg-gray-100 dark:hover:bg-gray-800
        ${isSelected ? 'bg-blue-50 text-blue-900' : ''}
      `}
    >
      {children}
    </div>
  );
}
