import React, { useEffect, useRef, useCallback } from 'react'

interface FocusTrapProps {
  children: React.ReactNode
  active: boolean
  restoreFocus?: boolean
  initialFocus?: React.RefObject<HTMLElement>
}

export function FocusTrap({ 
  children, 
  active, 
  restoreFocus = true,
  initialFocus 
}: FocusTrapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const previousActiveElement = useRef<HTMLElement | null>(null)

  const getFocusableElements = useCallback(() => {
    if (!containerRef.current) return []
    
    const focusableSelectors = [
      'button:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      'a[href]',
      '[tabindex]:not([tabindex="-1"])',
      '[contenteditable="true"]'
    ].join(', ')
    
    return Array.from(
      containerRef.current.querySelectorAll<HTMLElement>(focusableSelectors)
    ).filter(element => {
      return element.offsetWidth > 0 && 
             element.offsetHeight > 0 && 
             !element.hasAttribute('hidden')
    })
  }, [])

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (!active || event.key !== 'Tab') return

    const focusableElements = getFocusableElements()
    if (focusableElements.length === 0) return

    const firstElement = focusableElements[0]
    const lastElement = focusableElements[focusableElements.length - 1]

    if (event.shiftKey) {
      // Shift + Tab
      if (document.activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      }
    } else {
      // Tab
      if (document.activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    }
  }, [active, getFocusableElements])

  useEffect(() => {
    if (active) {
      // Store the currently focused element
      previousActiveElement.current = document.activeElement as HTMLElement
      
      // Focus the initial element or first focusable element
      const focusableElements = getFocusableElements()
      if (initialFocus?.current) {
        initialFocus.current.focus()
      } else if (focusableElements.length > 0) {
        focusableElements[0].focus()
      }
      
      // Add event listener
      document.addEventListener('keydown', handleKeyDown)
    } else if (restoreFocus && previousActiveElement.current) {
      // Restore focus to the previously focused element
      previousActiveElement.current.focus()
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [active, handleKeyDown, getFocusableElements, initialFocus, restoreFocus])

  return (
    <div ref={containerRef}>
      {children}
    </div>
  )
}

// Hook for managing focus
export function useFocusManagement() {
  const focusElement = useCallback((element: HTMLElement | null) => {
    if (element) {
      element.focus()
    }
  }, [])

  const focusById = useCallback((id: string) => {
    const element = document.getElementById(id)
    focusElement(element)
  }, [focusElement])

  const focusFirst = useCallback((container?: HTMLElement) => {
    const root = container || document.body
    const focusableElement = root.querySelector<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
    )
    focusElement(focusableElement)
  }, [focusElement])

  const focusLast = useCallback((container?: HTMLElement) => {
    const root = container || document.body
    const focusableElements = root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
    )
    if (focusableElements.length > 0) {
      focusElement(focusableElements[focusableElements.length - 1])
    }
  }, [focusElement])

  return {
    focusElement,
    focusById,
    focusFirst,
    focusLast,
  }
}

// Component for managing focus announcements
interface FocusAnnouncementProps {
  message: string
  priority?: 'polite' | 'assertive'
}

export function FocusAnnouncement({ message, priority = 'polite' }: FocusAnnouncementProps) {
  return (
    <div
      role="status"
      aria-live={priority}
      aria-atomic="true"
      className="sr-only"
    >
      {message}
    </div>
  )
}