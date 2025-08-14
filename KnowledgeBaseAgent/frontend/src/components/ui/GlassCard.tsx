import { cn } from '@/utils/cn';
import { ReactNode } from 'react';

interface GlassCardProps {
  className?: string;
  title?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function GlassCard({ className, title, children, footer }: GlassCardProps) {
  return (
    <div className={cn('rounded-xl border border-white/10 bg-white/10 backdrop-blur-md shadow-glass', className)}>
      {title && (
        <div className="px-4 py-3 border-b border-white/10">
          <h3 className="text-sm font-medium text-gray-900/90">{title}</h3>
        </div>
      )}
      <div className="p-4">{children}</div>
      {footer && <div className="px-4 py-3 border-t border-white/10">{footer}</div>}
    </div>
  );
}


