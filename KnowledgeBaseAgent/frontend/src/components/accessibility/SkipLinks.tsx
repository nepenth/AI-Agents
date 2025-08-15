import React from 'react'
import { cn } from '@/utils/cn'

interface SkipLink {
  href: string
  label: string
}

const defaultSkipLinks: SkipLink[] = [
  { href: '#main-content', label: 'Skip to main content' },
  { href: '#navigation', label: 'Skip to navigation' },
  { href: '#search', label: 'Skip to search' },
]

interface SkipLinksProps {
  links?: SkipLink[]
  className?: string
}

export function SkipLinks({ links = defaultSkipLinks, className }: SkipLinksProps) {
  return (
    <div className={cn('skip-links', className)}>
      {links.map((link) => (
        <a
          key={link.href}
          href={link.href}
          className={cn(
            'absolute left-0 top-0 z-50',
            'px-4 py-2 bg-primary text-primary-foreground',
            'text-sm font-medium rounded-br-md',
            'transform -translate-y-full',
            'focus:translate-y-0 focus:outline-none focus:ring-2 focus:ring-ring',
            'transition-transform duration-200'
          )}
        >
          {link.label}
        </a>
      ))}
    </div>
  )
}

// Screen reader only content
interface ScreenReaderOnlyProps {
  children: React.ReactNode
  as?: keyof JSX.IntrinsicElements
  className?: string
}

export function ScreenReaderOnly({ 
  children, 
  as: Component = 'span',
  className 
}: ScreenReaderOnlyProps) {
  return (
    <Component className={cn('sr-only', className)}>
      {children}
    </Component>
  )
}

// Visually hidden but accessible to screen readers
export function VisuallyHidden({ children, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      {...props}
      className={cn(
        'absolute w-px h-px p-0 -m-px overflow-hidden',
        'whitespace-nowrap border-0',
        'clip-path-inset-50',
        props.className
      )}
    >
      {children}
    </span>
  )
}