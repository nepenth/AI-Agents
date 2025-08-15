import React, { createContext, useContext, useState, useEffect } from 'react'

interface AccessibilitySettings {
  reduceMotion: boolean
  increaseContrast: boolean
  reduceTransparency: boolean
  largeText: boolean
  focusVisible: boolean
  screenReaderOptimized: boolean
  keyboardNavigation: boolean
}

interface AccessibilityContextType {
  settings: AccessibilitySettings
  updateSetting: <K extends keyof AccessibilitySettings>(
    key: K,
    value: AccessibilitySettings[K]
  ) => void
  resetSettings: () => void
  announceToScreenReader: (message: string, priority?: 'polite' | 'assertive') => void
}

const defaultSettings: AccessibilitySettings = {
  reduceMotion: false,
  increaseContrast: false,
  reduceTransparency: false,
  largeText: false,
  focusVisible: true,
  screenReaderOptimized: false,
  keyboardNavigation: true,
}

const AccessibilityContext = createContext<AccessibilityContextType | undefined>(undefined)

export function AccessibilityProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<AccessibilitySettings>(() => {
    // Load from localStorage
    const saved = localStorage.getItem('accessibility-settings')
    if (saved) {
      try {
        return { ...defaultSettings, ...JSON.parse(saved) }
      } catch {
        return defaultSettings
      }
    }

    // Detect system preferences
    const systemSettings = { ...defaultSettings }
    
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      systemSettings.reduceMotion = true
    }
    
    if (window.matchMedia('(prefers-contrast: high)').matches) {
      systemSettings.increaseContrast = true
    }
    
    if (window.matchMedia('(prefers-reduced-transparency: reduce)').matches) {
      systemSettings.reduceTransparency = true
    }

    return systemSettings
  })

  // Save to localStorage when settings change
  useEffect(() => {
    localStorage.setItem('accessibility-settings', JSON.stringify(settings))
  }, [settings])

  // Apply settings to document
  useEffect(() => {
    const root = document.documentElement
    
    // Apply CSS custom properties based on settings
    root.setAttribute('data-reduce-motion', settings.reduceMotion.toString())
    root.setAttribute('data-increase-contrast', settings.increaseContrast.toString())
    root.setAttribute('data-reduce-transparency', settings.reduceTransparency.toString())
    root.setAttribute('data-large-text', settings.largeText.toString())
    root.setAttribute('data-focus-visible', settings.focusVisible.toString())
    
    // Apply CSS classes
    root.classList.toggle('reduce-motion', settings.reduceMotion)
    root.classList.toggle('increase-contrast', settings.increaseContrast)
    root.classList.toggle('reduce-transparency', settings.reduceTransparency)
    root.classList.toggle('large-text', settings.largeText)
    root.classList.toggle('focus-visible-enabled', settings.focusVisible)
    root.classList.toggle('screen-reader-optimized', settings.screenReaderOptimized)
  }, [settings])

  // Listen for system preference changes
  useEffect(() => {
    const mediaQueries = [
      {
        query: window.matchMedia('(prefers-reduced-motion: reduce)'),
        setting: 'reduceMotion' as const
      },
      {
        query: window.matchMedia('(prefers-contrast: high)'),
        setting: 'increaseContrast' as const
      },
      {
        query: window.matchMedia('(prefers-reduced-transparency: reduce)'),
        setting: 'reduceTransparency' as const
      }
    ]

    const handlers = mediaQueries.map(({ query, setting }) => {
      const handler = (e: MediaQueryListEvent) => {
        setSettings(prev => ({ ...prev, [setting]: e.matches }))
      }
      query.addEventListener('change', handler)
      return { query, handler }
    })

    return () => {
      handlers.forEach(({ query, handler }) => {
        query.removeEventListener('change', handler)
      })
    }
  }, [])

  const updateSetting = <K extends keyof AccessibilitySettings>(
    key: K,
    value: AccessibilitySettings[K]
  ) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  const resetSettings = () => {
    setSettings(defaultSettings)
  }

  const announceToScreenReader = (message: string, priority: 'polite' | 'assertive' = 'polite') => {
    const announcement = document.createElement('div')
    announcement.setAttribute('aria-live', priority)
    announcement.setAttribute('aria-atomic', 'true')
    announcement.className = 'sr-only'
    announcement.textContent = message
    
    document.body.appendChild(announcement)
    
    // Remove after announcement
    setTimeout(() => {
      document.body.removeChild(announcement)
    }, 1000)
  }

  return (
    <AccessibilityContext.Provider
      value={{
        settings,
        updateSetting,
        resetSettings,
        announceToScreenReader,
      }}
    >
      {children}
    </AccessibilityContext.Provider>
  )
}

export function useAccessibility() {
  const context = useContext(AccessibilityContext)
  if (context === undefined) {
    throw new Error('useAccessibility must be used within an AccessibilityProvider')
  }
  return context
}