import React from 'react'
import { cn } from '@/utils/cn'

interface ResponsiveGridProps {
  children: React.ReactNode
  className?: string
  cols?: {
    xs?: number
    sm?: number
    md?: number
    lg?: number
    xl?: number
    '2xl'?: number
  }
  gap?: {
    xs?: number
    sm?: number
    md?: number
    lg?: number
    xl?: number
    '2xl'?: number
  }
}

export function ResponsiveGrid({ 
  children, 
  className,
  cols = { xs: 1, sm: 2, md: 2, lg: 3, xl: 4 },
  gap = { xs: 4, sm: 4, md: 6, lg: 6, xl: 8 }
}: ResponsiveGridProps) {
  const getColsClass = () => {
    const classes = []
    
    if (cols.xs) classes.push(`grid-cols-${cols.xs}`)
    if (cols.sm) classes.push(`sm:grid-cols-${cols.sm}`)
    if (cols.md) classes.push(`md:grid-cols-${cols.md}`)
    if (cols.lg) classes.push(`lg:grid-cols-${cols.lg}`)
    if (cols.xl) classes.push(`xl:grid-cols-${cols.xl}`)
    if (cols['2xl']) classes.push(`2xl:grid-cols-${cols['2xl']}`)
    
    return classes.join(' ')
  }

  const getGapClass = () => {
    const classes = []
    
    if (gap.xs) classes.push(`gap-${gap.xs}`)
    if (gap.sm) classes.push(`sm:gap-${gap.sm}`)
    if (gap.md) classes.push(`md:gap-${gap.md}`)
    if (gap.lg) classes.push(`lg:gap-${gap.lg}`)
    if (gap.xl) classes.push(`xl:gap-${gap.xl}`)
    if (gap['2xl']) classes.push(`2xl:gap-${gap['2xl']}`)
    
    return classes.join(' ')
  }

  return (
    <div className={cn(
      'grid',
      getColsClass(),
      getGapClass(),
      className
    )}>
      {children}
    </div>
  )
}

// Responsive container component
interface ResponsiveContainerProps {
  children: React.ReactNode
  className?: string
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
}

export function ResponsiveContainer({ 
  children, 
  className,
  size = 'xl'
}: ResponsiveContainerProps) {
  const sizeClasses = {
    sm: 'max-w-screen-sm',
    md: 'max-w-screen-md', 
    lg: 'max-w-screen-lg',
    xl: 'max-w-screen-xl',
    full: 'max-w-full'
  }

  return (
    <div className={cn(
      'mx-auto w-full',
      sizeClasses[size],
      'px-4 sm:px-6 lg:px-8',
      className
    )}>
      {children}
    </div>
  )
}

// Responsive stack component
interface ResponsiveStackProps {
  children: React.ReactNode
  className?: string
  direction?: {
    xs?: 'row' | 'col'
    sm?: 'row' | 'col'
    md?: 'row' | 'col'
    lg?: 'row' | 'col'
    xl?: 'row' | 'col'
  }
  gap?: {
    xs?: number
    sm?: number
    md?: number
    lg?: number
    xl?: number
  }
  align?: 'start' | 'center' | 'end' | 'stretch'
  justify?: 'start' | 'center' | 'end' | 'between' | 'around' | 'evenly'
}

export function ResponsiveStack({
  children,
  className,
  direction = { xs: 'col', lg: 'row' },
  gap = { xs: 4, sm: 4, md: 6 },
  align = 'start',
  justify = 'start'
}: ResponsiveStackProps) {
  const getDirectionClass = () => {
    const classes = []
    
    if (direction.xs) classes.push(`flex-${direction.xs}`)
    if (direction.sm) classes.push(`sm:flex-${direction.sm}`)
    if (direction.md) classes.push(`md:flex-${direction.md}`)
    if (direction.lg) classes.push(`lg:flex-${direction.lg}`)
    if (direction.xl) classes.push(`xl:flex-${direction.xl}`)
    
    return classes.join(' ')
  }

  const getGapClass = () => {
    const classes = []
    
    if (gap.xs) classes.push(`gap-${gap.xs}`)
    if (gap.sm) classes.push(`sm:gap-${gap.sm}`)
    if (gap.md) classes.push(`md:gap-${gap.md}`)
    if (gap.lg) classes.push(`lg:gap-${gap.lg}`)
    if (gap.xl) classes.push(`xl:gap-${gap.xl}`)
    
    return classes.join(' ')
  }

  const alignClasses = {
    start: 'items-start',
    center: 'items-center',
    end: 'items-end',
    stretch: 'items-stretch'
  }

  const justifyClasses = {
    start: 'justify-start',
    center: 'justify-center',
    end: 'justify-end',
    between: 'justify-between',
    around: 'justify-around',
    evenly: 'justify-evenly'
  }

  return (
    <div className={cn(
      'flex',
      getDirectionClass(),
      getGapClass(),
      alignClasses[align],
      justifyClasses[justify],
      className
    )}>
      {children}
    </div>
  )
}