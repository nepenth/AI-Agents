import { useState, useEffect } from 'react'

interface BreakpointConfig {
  sm: number
  md: number
  lg: number
  xl: number
  '2xl': number
}

const breakpoints: BreakpointConfig = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
}

export interface ResponsiveState {
  width: number
  height: number
  isMobile: boolean
  isTablet: boolean
  isDesktop: boolean
  isLargeDesktop: boolean
  breakpoint: keyof BreakpointConfig | 'xs'
  orientation: 'portrait' | 'landscape'
  isTouch: boolean
}

export function useResponsive(): ResponsiveState {
  const [state, setState] = useState<ResponsiveState>(() => {
    if (typeof window === 'undefined') {
      return {
        width: 1024,
        height: 768,
        isMobile: false,
        isTablet: false,
        isDesktop: true,
        isLargeDesktop: false,
        breakpoint: 'lg' as const,
        orientation: 'landscape' as const,
        isTouch: false,
      }
    }

    const width = window.innerWidth
    const height = window.innerHeight
    
    return {
      width,
      height,
      isMobile: width < breakpoints.md,
      isTablet: width >= breakpoints.md && width < breakpoints.lg,
      isDesktop: width >= breakpoints.lg,
      isLargeDesktop: width >= breakpoints.xl,
      breakpoint: getBreakpoint(width),
      orientation: height > width ? 'portrait' : 'landscape',
      isTouch: 'ontouchstart' in window || navigator.maxTouchPoints > 0,
    }
  })

  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth
      const height = window.innerHeight
      
      setState({
        width,
        height,
        isMobile: width < breakpoints.md,
        isTablet: width >= breakpoints.md && width < breakpoints.lg,
        isDesktop: width >= breakpoints.lg,
        isLargeDesktop: width >= breakpoints.xl,
        breakpoint: getBreakpoint(width),
        orientation: height > width ? 'portrait' : 'landscape',
        isTouch: 'ontouchstart' in window || navigator.maxTouchPoints > 0,
      })
    }

    window.addEventListener('resize', handleResize)
    window.addEventListener('orientationchange', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('orientationchange', handleResize)
    }
  }, [])

  return state
}

function getBreakpoint(width: number): keyof BreakpointConfig | 'xs' {
  if (width >= breakpoints['2xl']) return '2xl'
  if (width >= breakpoints.xl) return 'xl'
  if (width >= breakpoints.lg) return 'lg'
  if (width >= breakpoints.md) return 'md'
  if (width >= breakpoints.sm) return 'sm'
  return 'xs'
}

// Hook for specific breakpoint checks
export function useBreakpoint(breakpoint: keyof BreakpointConfig) {
  const { width } = useResponsive()
  return width >= breakpoints[breakpoint]
}

// Hook for mobile-specific behavior
export function useMobile() {
  const { isMobile, isTouch } = useResponsive()
  return { isMobile, isTouch }
}

// Hook for responsive values
export function useResponsiveValue<T>(values: {
  xs?: T
  sm?: T
  md?: T
  lg?: T
  xl?: T
  '2xl'?: T
}): T | undefined {
  const { breakpoint } = useResponsive()
  
  // Return the value for the current breakpoint or the closest smaller one
  const breakpointOrder: (keyof BreakpointConfig | 'xs')[] = ['xs', 'sm', 'md', 'lg', 'xl', '2xl']
  const currentIndex = breakpointOrder.indexOf(breakpoint)
  
  for (let i = currentIndex; i >= 0; i--) {
    const bp = breakpointOrder[i]
    if (values[bp] !== undefined) {
      return values[bp]
    }
  }
  
  return undefined
}