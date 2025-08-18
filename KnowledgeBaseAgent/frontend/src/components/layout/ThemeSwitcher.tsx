import * as React from 'react';
import { useThemeStore, type Theme, type AccentColor } from '@/stores/themeStore';
import { Sun, Moon, Laptop, Palette } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/DropdownMenu'; // Assuming DropdownMenu is available

const themeOptions: { value: Theme; label: string; icon: React.ElementType }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Laptop },
];

const accentColorOptions: { value: AccentColor; color: string }[] = [
  { value: 'blue', color: '#3b82f6' },
  { value: 'purple', color: '#8b5cf6' },
  { value: 'green', color: '#10b981' },
  { value: 'orange', color: '#f59e0b' },
  { value: 'pink', color: '#ec4899' },
];

export function ThemeSwitcher() {
  const { theme, accentColor, setTheme, setAccentColor } = useThemeStore();

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm">
            <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {themeOptions.map((option) => (
            <DropdownMenuItem key={option.value} onClick={() => setTheme(option.value)}>
              <option.icon className="mr-2 h-4 w-4" />
              <span>{option.label}</span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm">
            <Palette className="h-4 w-4" />
            <span className="sr-only">Change accent color</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <div className="grid grid-cols-5 gap-2 p-2">
            {accentColorOptions.map((option) => (
              <Button
                key={option.value}
                variant={accentColor === option.value ? 'default' : 'ghost'}
                size="sm"
                style={{ backgroundColor: accentColor === option.value ? option.color : undefined }}
                onClick={() => setAccentColor(option.value)}
              >
                <span style={{ color: option.color }}>●</span>
              </Button>
            ))}
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
