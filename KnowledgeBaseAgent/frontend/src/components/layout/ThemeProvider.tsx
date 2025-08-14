import { useEffect } from 'react';
import { useThemeStore } from '@/stores/themeStore';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { reduceTransparency, reduceMotion, increaseContrast } = useThemeStore();

  useEffect(() => {
    const root = window.document.documentElement;

    // Set data attributes for accessibility options
    root.setAttribute('data-theme-transparency', String(!!reduceTransparency));
    root.setAttribute('data-theme-motion', String(!!reduceMotion));
    root.setAttribute('data-theme-contrast', String(!!increaseContrast));

    // Handle dark mode based on system preference
    const darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleThemeChange = (e: MediaQueryListEvent) => {
      root.classList.toggle('dark', e.matches);
    };

    root.classList.toggle('dark', darkModeMediaQuery.matches);
    darkModeMediaQuery.addEventListener('change', handleThemeChange);

    return () => {
      darkModeMediaQuery.removeEventListener('change', handleThemeChange);
    };
  }, [reduceTransparency, reduceMotion, increaseContrast]);

  return <>{children}</>;
}
