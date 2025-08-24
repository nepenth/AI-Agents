/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['attr', 'data-theme'], // Enable dark mode using a data attribute
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        /* Apple-style Glass System Colors */
        'glass-primary': 'var(--glass-bg-primary)',
        'glass-secondary': 'var(--glass-bg-secondary)',
        'glass-tertiary': 'var(--glass-bg-tertiary)',
        'glass-navbar': 'var(--glass-bg-navbar)',
        'glass-interactive': 'var(--glass-bg-interactive)',
        'glass-overlay': 'var(--glass-bg-overlay)',
        
        /* Glass Border Colors */
        'glass-border-primary': 'var(--glass-border-primary)',
        'glass-border-secondary': 'var(--glass-border-secondary)',
        'glass-border-tertiary': 'var(--glass-border-tertiary)',
        'glass-border-navbar': 'var(--glass-border-navbar)',
        'glass-border-interactive': 'var(--glass-border-interactive)',
        'glass-border-overlay': 'var(--glass-border-overlay)',
        
        /* Legacy glass colors for backward compatibility */
        'glass-bg-primary': 'var(--glass-bg-primary)',
        'glass-bg-secondary': 'var(--glass-bg-secondary)',
        'glass-bg-tertiary': 'var(--glass-bg-tertiary)',
        'glass-border-primary': 'var(--glass-border-primary)',
        'glass-border-secondary': 'var(--glass-border-secondary)',
        'glass-border-tertiary': 'var(--glass-border-tertiary)',
        'glass-bg-navbar': 'var(--glass-bg-navbar)',
        'glass-button-bg': 'var(--glass-button-bg)',
        'glass-button-border': 'var(--glass-button-border)',
        'glass-card-bg': 'var(--glass-card-bg)',
        'glass-card-border': 'var(--glass-card-border)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        xl: 'var(--radius-xl)',
      },
      backdropBlur: {
        /* Apple-style Glass Blur System */
        'glass-primary': 'var(--glass-blur-primary)',
        'glass-secondary': 'var(--glass-blur-secondary)',
        'glass-tertiary': 'var(--glass-blur-tertiary)',
        'glass-navbar': 'var(--glass-blur-navbar)',
        'glass-interactive': 'var(--glass-blur-interactive)',
        'glass-overlay': 'var(--glass-blur-overlay)',
        
        /* Legacy blur utilities for backward compatibility */
        'glass-subtle': 'var(--glass-blur-subtle)',
        'glass-light': 'var(--glass-blur-light)',
        'glass-medium': 'var(--glass-blur-medium)',
        'glass-strong': 'var(--glass-blur-strong)',
        'glass-xl': 'var(--glass-blur-xl)',
        'glass-button': 'var(--glass-button-blur)',
        'glass-button-hover': 'var(--glass-button-hover-blur)',
        'glass-card': 'var(--glass-card-blur)',
      },
      boxShadow: {
        /* Apple-style Glass Shadow System */
        'glass-primary': 'var(--glass-shadow-primary)',
        'glass-secondary': 'var(--glass-shadow-secondary)',
        'glass-tertiary': 'var(--glass-shadow-tertiary)',
        'glass-navbar': 'var(--glass-shadow-navbar)',
        'glass-interactive': 'var(--glass-shadow-interactive)',
        'glass-interactive-hover': 'var(--glass-shadow-interactive-hover)',
        'glass-overlay': 'var(--glass-shadow-overlay)',
        
        /* Legacy shadow utilities for backward compatibility */
        'glass-sm': 'var(--glass-shadow-sm)',
        'glass-md': 'var(--glass-shadow-md)',
        'glass-lg': 'var(--glass-shadow-lg)',
        'glass-button': 'var(--glass-button-shadow)',
        'glass-button-hover': 'var(--glass-button-hover-shadow)',
        'glass-card': 'var(--glass-card-shadow)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s var(--ease-smooth)',
        'slide-up': 'slideUp 0.5s var(--ease-smooth)',
        'slide-in-bottom': 'slideInBottom 0.5s var(--ease-smooth)',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-in': 'bounceIn 0.5s var(--ease-spring)',
        'spring-in': 'springIn 0.5s var(--ease-spring)',
        'lift': 'lift var(--duration-normal) var(--ease-smooth)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideInBottom: {
          '0%': { transform: 'translateY(100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        bounceIn: {
            '0%': { transform: 'scale(0.5)', opacity: '0' },
            '100%': { transform: 'scale(1)', opacity: '1' },
        },
        springIn: {
            '0%': { transform: 'scale(0.9)', opacity: '0' },
            '100%': { transform: 'scale(1)', opacity: '1' },
        },
        lift: {
            '0%': { transform: 'translateY(0) scale(1)' },
            '100%': { transform: 'var(--transform-lift-md)' },
        }
      },
      spacing: {
        'safe-top': 'env(safe-area-inset-top)',
        'safe-bottom': 'env(safe-area-inset-bottom)',
        'safe-left': 'env(safe-area-inset-left)',
        'safe-right': 'env(safe-area-inset-right)',
      },
      minHeight: {
        'screen-mobile': ['100vh', '100dvh'],
      },
      screens: {
        'xs': '475px',
        'touch': { 'raw': '(hover: none) and (pointer: coarse)' },
        'no-touch': { 'raw': '(hover: hover) and (pointer: fine)' },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('tailwindcss-animate'), // For animation utilities
  ],
}