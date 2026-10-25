import { useEffect, useCallback } from 'react'

/**
 * Custom hook for handling keyboard shortcuts
 * @param {Object} shortcuts - Object mapping key combinations to handlers
 * @param {boolean} enabled - Whether shortcuts are enabled
 * 
 * Example:
 * useKeyboardShortcuts({
 *   'cmd+k': () => openSearch(),
 *   'cmd+/': () => openHelp(),
 *   'esc': () => closeModal(),
 * })
 */
export const useKeyboardShortcuts = (shortcuts, enabled = true) => {
  const handleKeyDown = useCallback(
    (event) => {
      if (!enabled) return

      // Build the key combination string
      const keys = []
      if (event.ctrlKey || event.metaKey) keys.push('cmd')
      if (event.shiftKey) keys.push('shift')
      if (event.altKey) keys.push('alt')
      
      const key = event.key.toLowerCase()
      if (!['control', 'meta', 'shift', 'alt'].includes(key)) {
        keys.push(key)
      }

      const combo = keys.join('+')

      // Check if we have a handler for this combination
      if (shortcuts[combo]) {
        event.preventDefault()
        shortcuts[combo](event)
      }
    },
    [shortcuts, enabled]
  )

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])
}

/**
 * Hook to check if user is on Mac
 */
export const useIsMac = () => {
  return typeof window !== 'undefined' && 
    navigator.platform.toUpperCase().indexOf('MAC') >= 0
}

/**
 * Format keyboard shortcut for display
 */
export const formatShortcut = (shortcut) => {
  const isMac = typeof window !== 'undefined' && 
    navigator.platform.toUpperCase().indexOf('MAC') >= 0
  
  return shortcut
    .split('+')
    .map(key => {
      if (key === 'cmd') return isMac ? '⌘' : 'Ctrl'
      if (key === 'shift') return isMac ? '⇧' : 'Shift'
      if (key === 'alt') return isMac ? '⌥' : 'Alt'
      return key.toUpperCase()
    })
    .join(isMac ? '' : '+')
}

export default useKeyboardShortcuts
