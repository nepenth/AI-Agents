import React from 'react'
import { cn } from '@/utils/cn'

interface SwitchProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  disabled?: boolean
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

export function Switch({ 
  checked, 
  onCheckedChange, 
  disabled = false, 
  className,
  size = 'md'
}: SwitchProps) {
  const sizeClasses = {
    sm: 'h-4 w-7',
    md: 'h-5 w-9',
    lg: 'h-6 w-11'
  }

  const thumbSizeClasses = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4', 
    lg: 'h-5 w-5'
  }

  const translateClasses = {
    sm: checked ? 'translate-x-3' : 'translate-x-0.5',
    md: checked ? 'translate-x-4' : 'translate-x-0.5',
    lg: checked ? 'translate-x-5' : 'translate-x-0.5'
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        'relative inline-flex shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        checked ? 'bg-primary' : 'bg-muted',
        sizeClasses[size],
        className
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-block rounded-full bg-white shadow transform ring-0 transition duration-200 ease-in-out',
          thumbSizeClasses[size],
          translateClasses[size]
        )}
      />
    </button>
  )
}