import { useEffect, useCallback, useRef } from 'react'

interface KeyboardNavigationOptions {
  enabled?: boolean
  trapFocus?: boolean
  restoreFocus?: boolean
  initialFocus?: string // CSS selector
}

export function useKeyboardNavigation(options: KeyboardNavigationOptions = {}) {
  const {
    enabled = true,
    trapFocus = false,
    restoreFocus = true,
    initialFocus
  } = options

  const containerRef = useRef<HTMLElement>(null)
  const previousActiveElement = useRef<Element | null>(null)

  const getFocusableElements = useCallback(() => {
    if (!containerRef.current) return []
    
    const focusableSelectors = [
      'button:not([disabled]):not([aria-hidden="true"])',
      'input:not([disabled]):not([aria-hidden="true"])',
      'select:not([disabled]):not([aria-hidden="true"])',
      'textarea:not([disabled]):not([aria-hidden="true"])',
      'a[href]:not([aria-hidden="true"])',
      '[tabindex]:not([tabindex="-1"]):not([aria-hidden="true"])',
      '[contenteditable="true"]:not([aria-hidden="true"])',
      '[role="button"]:not([disabled]):not([aria-hidden="true"])',
      '[role="link"]:not([aria-hidden="true"])',
      '[role="menuitem"]:not([disabled]):not([aria-hidden="true"])',
      '[role="tab"]:not([disabled]):not([aria-hidden="true"])'
    ].join(', ')
    
    return Array.from(
      containerRef.current.querySelectorAll<HTMLElement>(focusableSelectors)
    ).filter(element => {
      const style = window.getComputedStyle(element)
      return (
        element.offsetWidth > 0 && 
        element.offsetHeight > 0 && 
        style.visibility !== 'hidden' &&
        style.display !== 'none' &&
        !element.hasAttribute('hidden')
      )
    })
  }, [])

  const focusFirst = useCallback(() => {
    const focusableElements = getFocusableElements()
    if (focusableElements.length > 0) {
      focusableElements[0].focus()
    }
  }, [getFocusableElements])

  const focusLast = useCallback(() => {
    const focusableElements = getFocusableElements()
    if (focusableElements.length > 0) {
      focusableElements[focusableElements.length - 1].focus()
    }
  }, [getFocusableElements])

  const focusNext = useCallback(() => {
    const focusableElements = getFocusableElements()
    const currentIndex = focusableElements.indexOf(document.activeElement as HTMLElement)
    
    if (currentIndex >= 0 && currentIndex < focusableElements.length - 1) {
      focusableElements[currentIndex + 1].focus()
    } else if (trapFocus && focusableElements.length > 0) {
      focusableElements[0].focus()
    }
  }, [getFocusableElements, trapFocus])

  const focusPrevious = useCallback(() => {
    const focusableElements = getFocusableElements()
    const currentIndex = focusableElements.indexOf(document.activeElement as HTMLElement)
    
    if (currentIndex > 0) {
      focusableElements[currentIndex - 1].focus()
    } else if (trapFocus && focusableElements.length > 0) {
      focusableElements[focusableElements.length - 1].focus()
    }
  }, [getFocusableElements, trapFocus])

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (!enabled) return

    switch (event.key) {
      case 'Tab':
        if (trapFocus) {
          event.preventDefault()
          if (event.shiftKey) {
            focusPrevious()
          } else {
            focusNext()
          }
        }
        break
      
      case 'ArrowDown':
        if (event.ctrlKey || event.metaKey) {
          event.preventDefault()
          focusNext()
        }
        break
      
      case 'ArrowUp':
        if (event.ctrlKey || event.metaKey) {
          event.preventDefault()
          focusPrevious()
        }
        break
      
      case 'Home':
        if (event.ctrlKey || event.metaKey) {
          event.preventDefault()
          focusFirst()
        }
        break
      
      case 'End':
        if (event.ctrlKey || event.metaKey) {
          event.preventDefault()
          focusLast()
        }
        break
    }
  }, [enabled, trapFocus, focusNext, focusPrevious, focusFirst, focusLast])

  useEffect(() => {
    if (enabled) {
      // Store the currently focused element
      previousActiveElement.current = document.activeElement
      
      // Focus initial element if specified
      if (initialFocus) {
        const element = containerRef.current?.querySelector<HTMLElement>(initialFocus)
        if (element) {
          element.focus()
        }
      }
      
      // Add keyboard event listener
      document.addEventListener('keydown', handleKeyDown)
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      
      // Restore focus if needed
      if (restoreFocus && previousActiveElement.current instanceof HTMLElement) {
        previousActiveElement.current.focus()
      }
    }
  }, [enabled, initialFocus, handleKeyDown, restoreFocus])

  return {
    containerRef,
    focusFirst,
    focusLast,
    focusNext,
    focusPrevious,
    getFocusableElements
  }
}

// Hook for handling specific keyboard shortcuts
interface KeyboardShortcut {
  key: string
  ctrlKey?: boolean
  shiftKey?: boolean
  altKey?: boolean
  metaKey?: boolean
  callback: (event: KeyboardEvent) => void
  description?: string
}

export function useKeyboardShortcuts(shortcuts: KeyboardShortcut[], enabled = true) {
  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (event: KeyboardEvent) => {
      for (const shortcut of shortcuts) {
        const keyMatches = event.key.toLowerCase() === shortcut.key.toLowerCase()
        const ctrlMatches = !!shortcut.ctrlKey === event.ctrlKey
        const shiftMatches = !!shortcut.shiftKey === event.shiftKey
        const altMatches = !!shortcut.altKey === event.altKey
        const metaMatches = !!shortcut.metaKey === event.metaKey

        if (keyMatches && ctrlMatches && shiftMatches && altMatches && metaMatches) {
          event.preventDefault()
          shortcut.callback(event)
          break
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [shortcuts, enabled])
}

// Hook for roving tabindex pattern (useful for toolbars, menus, etc.)
export function useRovingTabIndex(orientation: 'horizontal' | 'vertical' = 'horizontal') {
  const containerRef = useRef<HTMLElement>(null)

  const updateTabIndex = useCallback((activeElement: HTMLElement) => {
    if (!containerRef.current) return

    const focusableElements = containerRef.current.querySelectorAll<HTMLElement>(
      '[role="tab"], [role="menuitem"], [role="option"], [role="gridcell"], [role="button"]'
    )

    focusableElements.forEach(element => {
      element.setAttribute('tabindex', element === activeElement ? '0' : '-1')
    })
  }, [])

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (!containerRef.current) return

    const target = event.target as HTMLElement
    const focusableElements = Array.from(
      containerRef.current.querySelectorAll<HTMLElement>(
        '[role="tab"], [role="menuitem"], [role="option"], [role="gridcell"], [role="button"]'
      )
    )

    const currentIndex = focusableElements.indexOf(target)
    if (currentIndex === -1) return

    let nextIndex = currentIndex

    switch (event.key) {
      case 'ArrowRight':
        if (orientation === 'horizontal') {
          event.preventDefault()
          nextIndex = (currentIndex + 1) % focusableElements.length
        }
        break
      
      case 'ArrowLeft':
        if (orientation === 'horizontal') {
          event.preventDefault()
          nextIndex = currentIndex === 0 ? focusableElements.length - 1 : currentIndex - 1
        }
        break
      
      case 'ArrowDown':
        if (orientation === 'vertical') {
          event.preventDefault()
          nextIndex = (currentIndex + 1) % focusableElements.length
        }
        break
      
      case 'ArrowUp':
        if (orientation === 'vertical') {
          event.preventDefault()
          nextIndex = currentIndex === 0 ? focusableElements.length - 1 : currentIndex - 1
        }
        break
      
      case 'Home':
        event.preventDefault()
        nextIndex = 0
        break
      
      case 'End':
        event.preventDefault()
        nextIndex = focusableElements.length - 1
        break
    }

    if (nextIndex !== currentIndex) {
      const nextElement = focusableElements[nextIndex]
      nextElement.focus()
      updateTabIndex(nextElement)
    }
  }, [orientation, updateTabIndex])

  const handleFocus = useCallback((event: FocusEvent) => {
    const target = event.target as HTMLElement
    updateTabIndex(target)
  }, [updateTabIndex])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // Initialize tabindex
    const focusableElements = container.querySelectorAll<HTMLElement>(
      '[role="tab"], [role="menuitem"], [role="option"], [role="gridcell"], [role="button"]'
    )
    
    if (focusableElements.length > 0) {
      updateTabIndex(focusableElements[0])
    }

    container.addEventListener('keydown', handleKeyDown)
    container.addEventListener('focus', handleFocus, true)

    return () => {
      container.removeEventListener('keydown', handleKeyDown)
      container.removeEventListener('focus', handleFocus, true)
    }
  }, [handleKeyDown, handleFocus, updateTabIndex])

  return { containerRef }
}