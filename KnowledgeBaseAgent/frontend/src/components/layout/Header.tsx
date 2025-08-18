import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, Bell, Search, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { WebSocketIndicator } from '@/components/ui/WebSocketIndicator';
import { ThemeSwitcher } from './ThemeSwitcher';
import { useWebSocket } from '@/hooks/useWebSocket';
import { cn } from '@/utils/cn';

const pageNames: Record<string, string> = {
  '/': 'Dashboard',
  '/knowledge': 'Knowledge Base',
  '/chat': 'Chat',
  '/monitoring': 'Monitoring',
  '/settings': 'Settings',
};

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const location = useLocation();
  const pageName = pageNames[location.pathname] || 'AI Agent';
  const [searchOpen, setSearchOpen] = useState(false);
  const { connectionStatus, lastConnected, reconnectAttempts, reconnect } = useWebSocket();

  return (
    <header className="bg-background border-b border-border">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14 sm:h-16">
          {/* Left Section */}
          <div className="flex items-center gap-3">
            {/* Mobile Menu Button */}
            <Button
              variant="ghost"
              size="sm"
              className="lg:hidden"
              onClick={onMenuClick}
            >
              <Menu className="h-5 w-5" />
            </Button>

            {/* Page Title */}
            <div className="flex items-center gap-3">
              <h1 className={cn(
                "font-semibold text-foreground",
                "text-lg sm:text-xl lg:text-2xl",
                searchOpen && "hidden sm:block"
              )}>
                {pageName}
              </h1>
              
              {/* Connection Status - Desktop */}
              <div className="hidden sm:block">
                <WebSocketIndicator 
                  status={connectionStatus}
                  lastConnected={lastConnected}
                  reconnectAttempts={reconnectAttempts}
                  onReconnect={reconnect}
                />
              </div>
            </div>
          </div>
          
          {/* Right Section */}
          <div className="flex items-center gap-2 sm:gap-4">
            {/* Search - Mobile Expandable */}
            <div className="flex items-center">
              {searchOpen ? (
                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <div className="relative flex-1 sm:w-64">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      type="text"
                      placeholder="Search..."
                      className="pl-10 pr-4 text-sm"
                      autoFocus
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="sm:hidden"
                    onClick={() => setSearchOpen(false)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <>
                  {/* Desktop Search */}
                  <div className="hidden sm:block relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      type="text"
                      placeholder="Search..."
                      className="pl-10 pr-4 w-64 text-sm"
                    />
                  </div>
                  
                  {/* Mobile Search Button */}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="sm:hidden"
                    onClick={() => setSearchOpen(true)}
                  >
                    <Search className="h-4 w-4" />
                  </Button>
                </>
              )}
            </div>
            
            {/* Theme Switcher */}
            <ThemeSwitcher />

            {/* Notifications */}
            <Button variant="ghost" size="sm" className="relative">
              <Bell className="h-4 w-4" />
              <span className="absolute -top-1 -right-1 h-2 w-2 bg-red-500 rounded-full" />
            </Button>

            {/* Connection Status - Mobile */}
            <div className="sm:hidden">
              <WebSocketIndicator 
                size="sm" 
                status={connectionStatus}
                lastConnected={lastConnected}
                reconnectAttempts={reconnectAttempts}
                onReconnect={reconnect}
                showLabel={false}
              />
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}