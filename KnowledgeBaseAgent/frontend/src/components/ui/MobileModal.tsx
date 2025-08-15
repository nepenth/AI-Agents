import React, { useEffect } from 'react'
import { X } from 'lucide-react'
import { Button } from './Button'
import { useResponsive } from '@/hooks/useResponsive'
import { cn } from '@/utils/cn'

interface MobileModalProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
  className?: string
  size?: 'sm' | 'md' | 'lg' | 'full'
  position?: 'center' | 'bottom'
}

export function MobileModal({
  isOpen,
  onClose,
  title,
  children,
  className,
  size = 'md',
  position = 'center'
}: MobileModalProps) {
  const { isMobile } = useResponsive()

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = 'unset'
      }
    }
  }, [isOpen])

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    full: 'max-w-full'
  }

  const mobilePositionClasses = {
    center: 'items-center justify-center p-4',
    bottom: 'items-end justify-center pb-0'
  }

  const desktopPositionClasses = {
    center: 'items-center justify-center p-4',
    bottom: 'items-center justify-center p-4'
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={onClose}
      />
      
      {/* Modal Container */}
      <div className={cn(
        'relative flex w-full',
        isMobile 
          ? mobilePositionClasses[position]
          : desktopPositionClasses[position]
      )}>
        {/* Modal Content */}
        <div className={cn(
          'relative bg-background border border-border shadow-lg',
          'w-full max-h-[90vh] overflow-hidden',
          // Mobile styles
          isMobile && position === 'bottom' && 'rounded-t-xl',
          isMobile && position === 'center' && 'rounded-xl',
          isMobile && size === 'full' && 'h-full max-h-none rounded-none',
          // Desktop styles
          !isMobile && 'rounded-xl',
          !isMobile && sizeClasses[size],
          className
        )}>
          {/* Header */}
          {title && (
            <div className="flex items-center justify-between p-4 border-b border-border">
              <h2 className="text-lg font-semibold text-foreground">
                {title}
              </h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                className="h-8 w-8 p-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}
          
          {/* Content */}
          <div className={cn(
            'overflow-y-auto',
            title ? 'max-h-[calc(90vh-4rem)]' : 'max-h-[90vh]',
            isMobile && size === 'full' && 'h-full max-h-none'
          )}>
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

// Mobile-optimized action sheet
interface ActionSheetProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  actions: Array<{
    label: string
    onClick: () => void
    variant?: 'default' | 'destructive'
    icon?: React.ComponentType<{ className?: string }>
  }>
}

export function ActionSheet({ isOpen, onClose, title, actions }: ActionSheetProps) {
  const { isMobile } = useResponsive()

  if (!isMobile) {
    // Render as regular modal on desktop
    return (
      <MobileModal isOpen={isOpen} onClose={onClose} title={title} size="sm">
        <div className="p-4 space-y-2">
          {actions.map((action, index) => (
            <Button
              key={index}
              variant={action.variant || 'outline'}
              onClick={() => {
                action.onClick()
                onClose()
              }}
              className="w-full justify-start"
            >
              {action.icon && <action.icon className="h-4 w-4 mr-2" />}
              {action.label}
            </Button>
          ))}
        </div>
      </MobileModal>
    )
  }

  return (
    <MobileModal 
      isOpen={isOpen} 
      onClose={onClose} 
      position="bottom"
      className="rounded-t-xl"
    >
      <div className="p-4">
        {title && (
          <div className="text-center mb-4">
            <div className="w-12 h-1 bg-muted rounded-full mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-foreground">{title}</h3>
          </div>
        )}
        
        <div className="space-y-2">
          {actions.map((action, index) => (
            <Button
              key={index}
              variant={action.variant || 'outline'}
              size="lg"
              onClick={() => {
                action.onClick()
                onClose()
              }}
              className="w-full justify-start h-12 text-base"
            >
              {action.icon && <action.icon className="h-5 w-5 mr-3" />}
              {action.label}
            </Button>
          ))}
        </div>
        
        <Button
          variant="outline"
          size="lg"
          onClick={onClose}
          className="w-full mt-4 h-12"
        >
          Cancel
        </Button>
      </div>
    </MobileModal>
  )
}