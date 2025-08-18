import { NavLink } from 'react-router-dom';
import { Home, BookOpen, MessageSquare, BarChart3, Settings, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
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
    <div className="flex flex-col w-64 h-full bg-glass-bg-secondary border-r border-glass-border-secondary backdrop-blur-glass-strong">
      {/* Header */}
      <div className="flex items-center justify-between h-14 sm:h-16 px-4 sm:px-6 border-b border-border">
        <h1 className="text-lg sm:text-xl font-semibold text-foreground">AI Agent</h1>
        
        {/* Mobile Close Button */}
        {onClose && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="lg:hidden"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
      
      {/* Navigation */}
      <nav className="flex-1 px-3 sm:px-4 py-4 sm:py-6 space-y-1 sm:space-y-2">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            onClick={onClose} // Close mobile sidebar on navigation
            className={({ isActive }) =>
              cn(
                'flex items-center px-3 py-2.5 sm:py-2 text-sm font-medium rounded-lg transition-colors',
                'touch-manipulation', // Better touch targets
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )
            }
          >
            <item.icon className="w-5 h-5 mr-3 flex-shrink-0" />
            <span className="truncate">{item.name}</span>
          </NavLink>
        ))}
      </nav>
      
      {/* User Profile */}
      <div className="p-3 sm:p-4 border-t border-border">
        <div className="flex items-center">
          <div className="w-8 h-8 sm:w-10 sm:h-10 bg-primary rounded-full flex items-center justify-center flex-shrink-0">
            <span className="text-sm font-medium text-primary-foreground">U</span>
          </div>
          <div className="ml-3 min-w-0 flex-1">
            <p className="text-sm font-medium text-foreground truncate">User</p>
            <p className="text-xs text-muted-foreground truncate">user@example.com</p>
          </div>
        </div>
      </div>
    </div>
  );
}