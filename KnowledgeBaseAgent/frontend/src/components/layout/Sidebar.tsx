import { NavLink } from 'react-router-dom';
import { Home, BookOpen, MessageSquare, BarChart3, Settings, X } from 'lucide-react';
import { LiquidButton } from '@/components/ui/LiquidButton';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { cn } from '@/utils/cn';

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Knowledge Base', href: '/knowledge', icon: BookOpen },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Monitoring', href: '/monitoring', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
];

interface SidebarProps {
  onClose?: () => void;
}

export function Sidebar({ onClose }: SidebarProps) {
  return (
    <GlassPanel 
      variant="navbar" 
      className="flex flex-col w-64 h-full border-r-0 rounded-none"
    >
      {/* Header */}
      <div className="flex items-center justify-between h-14 sm:h-16 px-4 sm:px-6 border-b border-glass-border-navbar relative z-10">
        <h1 className="text-lg sm:text-xl font-semibold text-foreground">AI Agent</h1>
        
        {/* Mobile Close Button */}
        {onClose && (
          <LiquidButton
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            className="lg:hidden"
          >
            <X className="h-4 w-4" />
          </LiquidButton>
        )}
      </div>
      
      {/* Navigation */}
      <nav className="flex-1 px-3 sm:px-4 py-4 sm:py-6 space-y-1 sm:space-y-2 relative z-10">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            onClick={onClose} // Close mobile sidebar on navigation
            className={({ isActive }) =>
              cn(
                'flex items-center px-4 py-3 text-sm font-medium rounded-xl transition-all duration-300 ease-out',
                'touch-manipulation relative overflow-hidden', // Better touch targets
                'before:absolute before:inset-0 before:bg-gradient-to-r before:from-white/5 before:to-transparent before:pointer-events-none',
                'hover:backdrop-blur-glass-secondary hover:bg-glass-secondary hover:border hover:border-glass-border-secondary hover:shadow-glass-secondary',
                'hover:scale-[1.02] hover:-translate-y-0.5',
                isActive
                  ? 'bg-glass-primary border border-glass-border-primary shadow-glass-primary backdrop-blur-glass-primary text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              )
            }
          >
            <item.icon className="w-5 h-5 mr-3 flex-shrink-0 relative z-10" />
            <span className="truncate relative z-10">{item.name}</span>
          </NavLink>
        ))}
      </nav>
      
      {/* User Profile */}
      <div className="p-3 sm:p-4 border-t border-glass-border-navbar relative z-10">
        <div className="flex items-center p-3 rounded-xl bg-glass-tertiary border border-glass-border-tertiary backdrop-blur-glass-tertiary shadow-glass-tertiary transition-all duration-300 hover:bg-glass-secondary hover:shadow-glass-secondary">
          <div className="w-8 h-8 sm:w-10 sm:h-10 bg-gradient-to-br from-primary to-primary/80 rounded-full flex items-center justify-center flex-shrink-0 shadow-glass-tertiary">
            <span className="text-sm font-medium text-primary-foreground">U</span>
          </div>
          <div className="ml-3 min-w-0 flex-1">
            <p className="text-sm font-medium text-foreground truncate">User</p>
            <p className="text-xs text-muted-foreground truncate">user@example.com</p>
          </div>
        </div>
      </div>
    </GlassPanel>
  );
}