import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'light' | 'dark' | 'system';
export type AccentColor = 'blue' | 'purple' | 'green' | 'orange' | 'pink';

export type ThemeState = {
  theme: Theme;
  accentColor: AccentColor;
  reduceTransparency: boolean;
  reduceMotion: boolean;
  increaseContrast: boolean;
};

type ThemeActions = {
  setTheme: (theme: Theme) => void;
  setAccentColor: (color: AccentColor) => void;
  setReduceTransparency: (value: boolean) => void;
  setReduceMotion: (value: boolean) => void;
  setIncreaseContrast: (value: boolean) => void;
};

export const useThemeStore = create<ThemeState & ThemeActions>()(
  persist(
    (set) => ({
      theme: 'system',
      accentColor: 'blue',
      reduceTransparency: false,
      reduceMotion: false,
      increaseContrast: false,
      setTheme: (theme) => set({ theme }),
      setAccentColor: (color) => set({ accentColor: color }),
      setReduceTransparency: (value) => set({ reduceTransparency: value }),
      setReduceMotion: (value) => set({ reduceMotion: value }),
      setIncreaseContrast: (value) => set({ increaseContrast: value }),
    }),
    {
      name: 'kb-agent-theme-settings', // name of the item in the storage (must be unique)
    }
  )
);
