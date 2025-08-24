import React from 'react';
import { cn } from '@/utils/cn';
import { useResponsive } from '@/hooks/useResponsive';

interface PageLayoutProps {
  children: React.ReactNode;
  className?: string;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full';
  spacing?: 'sm' | 'md' | 'lg' | 'xl';
  paddingX?: boolean;
  paddingY?: boolean;
}

/**
 * Standardized page layout component that ensures consistent:
 * - Spacing from navigation bar
 * - Container max-widths
 * - Responsive padding
 * - Vertical rhythm
 */
export function PageLayout({
  children,
  className,
  maxWidth = 'xl', // Default to xl for most pages
  spacing = 'lg', // Default to large spacing
  paddingX = true,
  paddingY = true
}: PageLayoutProps) {
  // Currently not using responsive data but keeping for future enhancements
  // const { isMobile, isTablet } = useResponsive();

  const maxWidthClasses = {
    sm: 'max-w-screen-sm',    // 640px
    md: 'max-w-screen-md',    // 768px
    lg: 'max-w-screen-lg',    // 1024px
    xl: 'max-w-screen-xl',    // 1280px
    '2xl': 'max-w-screen-2xl', // 1536px
    full: 'max-w-full'
  };

  const spacingClasses = {
    sm: {
      paddingY: 'py-4 sm:py-6',
      paddingX: 'px-4 sm:px-6',
      gap: 'space-y-4 sm:space-y-6'
    },
    md: {
      paddingY: 'py-6 sm:py-8',
      paddingX: 'px-4 sm:px-6 lg:px-8',
      gap: 'space-y-6 sm:space-y-8'
    },
    lg: {
      paddingY: 'py-6 sm:py-8 lg:py-10',
      paddingX: 'px-4 sm:px-6 lg:px-8',
      gap: 'space-y-6 sm:space-y-8 lg:space-y-10'
    },
    xl: {
      paddingY: 'py-8 sm:py-10 lg:py-12',
      paddingX: 'px-6 sm:px-8 lg:px-12',
      gap: 'space-y-8 sm:space-y-10 lg:space-y-12'
    }
  };

  const spacingConfig = spacingClasses[spacing];

  return (
    <div className={cn(
      'min-h-full w-full',
      // Consistent top spacing to account for header
      'pt-4 sm:pt-6',
      className
    )}>
      <div className={cn(
        'mx-auto w-full',
        maxWidthClasses[maxWidth],
        paddingX && spacingConfig.paddingX,
        paddingY && spacingConfig.paddingY
      )}>
        <div className={spacingConfig.gap}>
          {children}
        </div>
      </div>
    </div>
  );
}

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

/**
 * Standardized page header component with consistent typography and spacing
 */
export function PageHeader({
  title,
  description,
  actions,
  children,
  className
}: PageHeaderProps) {
  const { isMobile } = useResponsive();

  return (
    <div className={cn('space-y-4', className)}>
      <div className={cn(
        'flex flex-col gap-4',
        actions && 'sm:flex-row sm:items-start sm:justify-between'
      )}>
        <div className="space-y-2">
          <h1 className={cn(
            'font-bold tracking-tight text-foreground',
            isMobile ? 'text-2xl' : 'text-3xl'
          )}>
            {title}
          </h1>
          {description && (
            <p className={cn(
              'text-muted-foreground',
              isMobile ? 'text-sm' : 'text-base'
            )}>
              {description}
            </p>
          )}
        </div>
        
        {actions && (
          <div className="flex-shrink-0">
            {actions}
          </div>
        )}
      </div>
      
      {children && (
        <div>
          {children}
        </div>
      )}
    </div>
  );
}

interface PageSectionProps {
  children: React.ReactNode;
  className?: string;
  spacing?: 'sm' | 'md' | 'lg';
  background?: 'none' | 'subtle' | 'glass';
}

/**
 * Standardized page section for consistent spacing between major page areas
 */
export function PageSection({
  children,
  className,
  spacing = 'md',
  background = 'none'
}: PageSectionProps) {
  const spacingClasses = {
    sm: 'space-y-4',
    md: 'space-y-6',
    lg: 'space-y-8'
  };

  const backgroundClasses = {
    none: '',
    subtle: 'bg-muted/5 rounded-lg p-6',
    glass: 'bg-glass-tertiary border border-glass-border-tertiary backdrop-blur-glass-tertiary rounded-xl p-6'
  };

  return (
    <section className={cn(
      spacingClasses[spacing],
      backgroundClasses[background],
      className
    )}>
      {children}
    </section>
  );
}

interface PageContentProps {
  children: React.ReactNode;
  className?: string;
  layout?: 'single' | 'sidebar' | 'grid' | 'masonry';
  gap?: 'sm' | 'md' | 'lg' | 'xl';
}

/**
 * Content area with standardized layouts for common page patterns
 */
export function PageContent({
  children,
  className,
  layout = 'single',
  gap = 'md'
}: PageContentProps) {
  const gapClasses = {
    sm: 'gap-4',
    md: 'gap-6',
    lg: 'gap-8',
    xl: 'gap-10'
  };

  const layoutClasses = {
    single: '',
    sidebar: 'lg:grid lg:grid-cols-12 lg:gap-8',
    grid: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
    masonry: 'columns-1 md:columns-2 lg:columns-3'
  };

  return (
    <div className={cn(
      layoutClasses[layout],
      layout !== 'single' && gapClasses[gap],
      className
    )}>
      {children}
    </div>
  );
}