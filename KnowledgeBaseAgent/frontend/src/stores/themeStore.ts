import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ThemeState = {
  reduceTransparency: boolean;
  reduceMotion: boolean;
  increaseContrast: boolean;
};

type ThemeActions = {
  setReduceTransparency: (value: boolean) => void;
  setReduceMotion: (value: boolean) => void;
  setIncreaseContrast: (value: boolean) => void;
  toggleReduceTransparency: () => void;
  toggleReduceMotion: () => void;
  toggleIncreaseContrast: () => void;
};

export const useThemeStore = create<ThemeState & ThemeActions>()(
  persist(
    (set) => ({
      reduceTransparency: false,
      reduceMotion: false,
      increaseContrast: false,
      setReduceTransparency: (value) => set({ reduceTransparency: value }),
      setReduceMotion: (value) => set({ reduceMotion: value }),
      setIncreaseContrast: (value) => set({ increaseContrast: value }),
      toggleReduceTransparency: () => set((state) => ({ reduceTransparency: !state.reduceTransparency })),
      toggleReduceMotion: () => set((state) => ({ reduceMotion: !state.reduceMotion })),
      toggleIncreaseContrast: () => set((state) => ({ increaseContrast: !state.increaseContrast })),
    }),
    {
      name: 'kb-agent-theme-settings', // name of the item in the storage (must be unique)
    }
  )
);
