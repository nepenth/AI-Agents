import { useEffect } from "react";
import { useThemeStore } from "@/stores/themeStore";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { theme, reduceTransparency, reduceMotion, increaseContrast } =
    useThemeStore();

  useEffect(() => {
    const root = window.document.documentElement;

    // Set data attributes for accessibility options
    root.setAttribute("data-theme-transparency", String(!!reduceTransparency));
    root.setAttribute("data-theme-motion", String(!!reduceMotion));
    root.setAttribute("data-theme-contrast", String(!!increaseContrast));
  }, [reduceTransparency, reduceMotion, increaseContrast]);

  useEffect(() => {
    const root = window.document.documentElement;

    if (theme === "system") {
      const darkModeMediaQuery = window.matchMedia(
        "(prefers-color-scheme: dark)"
      );
      const handleThemeChange = (e: MediaQueryListEvent) => {
        root.classList.toggle("dark", e.matches);
      };

      root.classList.toggle("dark", darkModeMediaQuery.matches);
      darkModeMediaQuery.addEventListener("change", handleThemeChange);

      return () => {
        darkModeMediaQuery.removeEventListener("change", handleThemeChange);
      };
    } else {
      root.classList.toggle("dark", theme === "dark");
    }
  }, [theme]);

  return <>{children}</>;
}
