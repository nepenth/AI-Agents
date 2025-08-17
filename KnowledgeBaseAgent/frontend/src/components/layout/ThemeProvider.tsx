import { useEffect } from 'react';
import { useThemeStore } from '@/stores/themeStore';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { theme, reduceTransparency, reduceMotion, increaseContrast } =
    useThemeStore();

  useEffect(() => {
    const root = document.documentElement;

    // Set accessibility attributes according to the architecture specification
    root.setAttribute('data-reduce-transparency', String(reduceTransparency));
    root.setAttribute('data-reduce-motion', String(reduceMotion));
    root.setAttribute('data-increase-contrast', String(increaseContrast));

    // This function sets the data-theme attribute on the root element
    const applyTheme = (themeValue: 'light' | 'dark') => {
      root.setAttribute('data-theme', themeValue);
    };

    if (theme === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

      // Handler to set theme based on system preference
      const handleSystemThemeChange = (e: MediaQueryListEvent) => {
        applyTheme(e.matches ? 'dark' : 'light');
      };

      // Set the initial theme based on the current system preference
      handleSystemThemeChange(mediaQuery);

      // Listen for changes in system theme preference
      mediaQuery.addEventListener('change', handleSystemThemeChange);

      // Cleanup listener on component unmount
      return () => {
        mediaQuery.removeEventListener('change', handleSystemThemeChange);
      };
    } else {
      // Apply the theme directly if it's 'light' or 'dark'
      applyTheme(theme);
    }
  }, [theme, reduceTransparency, reduceMotion, increaseContrast]);

  return <>{children}</>;
}
