import { NavLink, useLocation } from 'react-router-dom';
import { Home, BookOpen, MessageSquare, BarChart3, Settings } from 'lucide-react';
import { cn } from '@/utils/cn';

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home, shortName: 'Home' },
  { name: 'Knowledge', href: '/knowledge', icon: BookOpen, shortName: 'Knowledge' },
  { name: 'Chat', href: '/chat', icon: MessageSquare, shortName: 'Chat' },
  { name: 'Monitor', href: '/monitoring', icon: BarChart3, shortName: 'Monitor' },
  { name: 'Settings', href: '/settings', icon: Settings, shortName: 'Settings' },
];

export function MobileNavigation() {
  const location = useLocation();

  return (
    <div className="fixed bottom-0 left-0 right-0 z-30 bg-background border-t border-border">
      <nav className="flex items-center justify-around px-2 py-2">
        {navigation.map((item) => {
          const isActive = location.pathname === item.href;
          
          return (
            <NavLink
              key={item.name}
              to={item.href}
              className={cn(
                'flex flex-col items-center justify-center px-2 py-1.5 rounded-lg transition-colors',
                'min-w-0 flex-1 max-w-[80px]', // Responsive width
                'touch-manipulation', // Better touch targets
                isActive
                  ? 'text-primary bg-primary/10'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent'
              )}
            >
              <item.icon className={cn(
                'flex-shrink-0 mb-1',
                'w-5 h-5 sm:w-6 sm:h-6'
              )} />
              <span className={cn(
                'text-xs font-medium truncate w-full text-center',
                'leading-tight'
              )}>
                {item.shortName}
              </span>
            </NavLink>
          );
        })}
      </nav>
      
      {/* Safe area padding for devices with home indicator */}
      <div className="h-safe-area-inset-bottom" />
    </div>
  );
}