import { Moon, Sun, Monitor } from 'lucide-react';
import { useThemeStore } from '@/stores/themeStore';
import { Button } from '@/components/ui/Button';

export function ThemeToggle() {
  const { theme, setTheme } = useThemeStore();

  return (
    <div className="flex items-center gap-2">
      <Button
        variant={theme === 'light' ? 'secondary' : 'ghost'}
        size="icon"
        onClick={() => setTheme('light')}
        aria-label="Switch to light theme"
      >
        <Sun className="h-5 w-5" />
      </Button>
      <Button
        variant={theme === 'dark' ? 'secondary' : 'ghost'}
        size="icon"
        onClick={() => setTheme('dark')}
        aria-label="Switch to dark theme"
      >
        <Moon className="h-5 w-5" />
      </Button>
      <Button
        variant={theme === 'system' ? 'secondary' : 'ghost'}
        size="icon"
        onClick={() => setTheme('system')}
        aria-label="Switch to system theme"
      >
        <Monitor className="h-5 w-5" />
      </Button>
    </div>
  );
}
