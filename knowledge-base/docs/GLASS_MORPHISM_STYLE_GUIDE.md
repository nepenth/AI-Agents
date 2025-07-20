# Glass Morphism UI Style Guide

## Overview

This style guide documents the Apple-inspired liquid glass UI system implemented for the Knowledge Base Agent. The system provides a comprehensive set of components, utilities, and patterns for creating modern, accessible, and performant user interfaces.

## Table of Contents

1. [Design Principles](#design-principles)
2. [Core Components](#core-components)
3. [CSS Architecture](#css-architecture)
4. [Component Usage](#component-usage)
5. [Theme System](#theme-system)
6. [Accessibility Guidelines](#accessibility-guidelines)
7. [Performance Considerations](#performance-considerations)
8. [Browser Support](#browser-support)
9. [Troubleshooting](#troubleshooting)

## Design Principles

### 1. Glass Morphism Aesthetic
- **Translucent backgrounds** with backdrop-filter blur effects
- **Subtle borders** with semi-transparent colors
- **Layered depth** through shadow and blur combinations
- **Smooth animations** with physics-based easing

### 2. Accessibility First
- **WCAG 2.1 AA compliance** for color contrast
- **Keyboard navigation** support for all interactive elements
- **Screen reader compatibility** with proper ARIA labels
- **Reduced motion** support for accessibility preferences

### 3. Performance Optimized
- **GPU acceleration** for smooth animations
- **Efficient CSS** with minimal repaints and reflows
- **Progressive enhancement** with graceful fallbacks
- **Mobile optimization** with reduced complexity on smaller screens

## Core Components

### Glass Panel System

The foundation of our glass morphism system consists of three primary panel types:

#### `.glass-panel-v3` (Primary)
```css
/* Primary glass panel with maximum blur and transparency */
.glass-panel-v3 {
  background: var(--glass-bg-primary);
  backdrop-filter: var(--glass-blur-medium) var(--glass-saturate);
  border: 1px solid var(--glass-border-primary);
  border-radius: var(--radius-xl);
  box-shadow: var(--glass-shadow-md);
}
```

**Usage:**
```html
<div class="glass-panel-v3">
  <h2>Primary Content Panel</h2>
  <p>Main content with maximum glass effect.</p>
</div>
```

#### `.glass-panel-v3--secondary` (Secondary)
```css
/* Secondary glass panel with medium blur */
.glass-panel-v3--secondary {
  background: var(--glass-bg-secondary);
  backdrop-filter: var(--glass-blur-light) var(--glass-saturate);
  border: 1px solid var(--glass-border-secondary);
}
```

**Usage:**
```html
<div class="glass-panel-v3--secondary">
  <h3>Secondary Content</h3>
  <p>Supporting content with medium glass effect.</p>
</div>
```

#### `.glass-panel-v3--tertiary` (Tertiary)
```css
/* Tertiary glass panel with subtle blur */
.glass-panel-v3--tertiary {
  background: var(--glass-bg-tertiary);
  backdrop-filter: var(--glass-blur-subtle) var(--glass-saturate);
  border: 1px solid var(--glass-border-tertiary);
}
```

**Usage:**
```html
<div class="glass-panel-v3--tertiary">
  <p>Subtle background content with minimal glass effect.</p>
</div>
```

### Liquid Button System

Interactive buttons with glass morphism and smooth animations:

#### Primary Button
```html
<button class="liquid-button liquid-button--primary animate-lift-hover">
  <i class="fas fa-play"></i>
  <span>Primary Action</span>
</button>
```

#### Secondary Button
```html
<button class="liquid-button liquid-button--secondary animate-lift-hover">
  <i class="fas fa-edit"></i>
  <span>Secondary Action</span>
</button>
```

#### Ghost Button
```html
<button class="liquid-button liquid-button--ghost animate-lift-hover">
  <i class="fas fa-times"></i>
  <span>Cancel</span>
</button>
```

#### Button Sizes
```html
<!-- Small -->
<button class="liquid-button liquid-button--primary liquid-button--sm">Small</button>

<!-- Default -->
<button class="liquid-button liquid-button--primary">Default</button>

<!-- Large -->
<button class="liquid-button liquid-button--primary liquid-button--lg">Large</button>
```

### Form Elements

#### Glass Input Fields
```html
<input type="text" class="glass-input" placeholder="Enter text...">
<textarea class="glass-input" placeholder="Enter message..."></textarea>
<select class="glass-input">
  <option>Select option</option>
</select>
```

#### Theme Controls
```html
<!-- Color picker -->
<div class="theme-color-grid">
  <button class="theme-color-btn active" data-theme="blue" title="Blue">
    <i class="fas fa-check"></i>
  </button>
</div>

<!-- Checkbox -->
<label class="theme-checkbox-label">
  <input type="checkbox" class="theme-checkbox">
  <span class="theme-checkbox-custom"></span>
  <span>Option label</span>
</label>
```

### Navigation Components

#### Liquid Navigation
```html
<nav class="liquid-nav">
  <div class="liquid-nav-indicator"></div>
  <a href="#" class="liquid-nav-item active">
    <i class="fas fa-home"></i>
    <span class="nav-text">Home</span>
  </a>
  <a href="#" class="liquid-nav-item">
    <i class="fas fa-user"></i>
    <span class="nav-text">Profile</span>
  </a>
</nav>
```

## CSS Architecture

### File Structure
```
v2/css/
├── core/
│   ├── reset.css              # CSS reset and normalization
│   ├── variables.css          # CSS custom properties and themes
│   ├── animations.css         # Animation keyframes and utilities
│   ├── mobile-optimizations.css    # Mobile-specific optimizations
│   └── browser-compatibility.css   # Cross-browser compatibility
├── components/
│   ├── glass-system.css       # Core glass morphism components
│   ├── sidebar-nav.css        # Navigation and theme components
│   ├── gpu-status.css         # GPU status display components
│   ├── chat-interface.css     # Chat interface components
│   └── knowledge-base.css     # Knowledge base explorer components
```

### CSS Custom Properties

#### Glass Morphism Variables
```css
:root {
  /* Glass backgrounds */
  --glass-bg-primary: rgba(255, 255, 255, 0.8);
  --glass-bg-secondary: rgba(255, 255, 255, 0.6);
  --glass-bg-tertiary: rgba(255, 255, 255, 0.4);
  
  /* Glass borders */
  --glass-border-primary: rgba(255, 255, 255, 0.3);
  --glass-border-secondary: rgba(255, 255, 255, 0.2);
  
  /* Glass blur effects */
  --glass-blur-subtle: blur(8px);
  --glass-blur-light: blur(12px);
  --glass-blur-medium: blur(16px);
  --glass-blur-strong: blur(20px);
  --glass-saturate: saturate(180%);
  
  /* Glass shadows */
  --glass-shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --glass-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --glass-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}
```

#### Animation Variables
```css
:root {
  /* Durations */
  --duration-fast: 0.15s;
  --duration-normal: 0.3s;
  --duration-slow: 0.5s;
  
  /* Easing functions */
  --ease-smooth: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
  --ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
  
  /* Transform utilities */
  --transform-lift-sm: translateY(-2px) scale(1.02);
  --transform-lift-md: translateY(-4px) scale(1.05);
  --transform-lift-lg: translateY(-8px) scale(1.08);
}
```

## Animation System

### Core Animation Classes

#### Entrance Animations
```html
<!-- Slide in from bottom -->
<div class="animate-glass-slide-in">Content</div>

<!-- Fade in -->
<div class="animate-glass-fade-in">Content</div>

<!-- Bounce in -->
<div class="animate-bounce-in">Content</div>

<!-- Spring scale -->
<div class="animate-spring-in">Content</div>
```

#### Hover Effects
```html
<!-- Lift on hover -->
<button class="animate-lift-hover">Hover me</button>

<!-- Float animation -->
<div class="animate-float-hover">Floating element</div>

<!-- Magnetic effect -->
<button class="animate-magnetic-hover">Magnetic button</button>
```

#### Loading States
```html
<!-- Shimmer effect -->
<div class="animate-shimmer-strong">Loading content</div>

<!-- Pulse animation -->
<div class="animate-loading-pulse">Loading...</div>

<!-- Glass breathing -->
<div class="animate-glass-breathe">Breathing effect</div>
```

### Stagger Animations
```html
<div class="animate-glass-slide-in animate-stagger-1">Item 1</div>
<div class="animate-glass-slide-in animate-stagger-2">Item 2</div>
<div class="animate-glass-slide-in animate-stagger-3">Item 3</div>
```

## Theme System

### Theme Modes
- **Light Mode**: Default bright theme with subtle glass effects
- **Dark Mode**: Dark theme with enhanced glass contrast
- **Auto Mode**: Automatically switches based on system preference

### Accent Colors
- **Blue** (default): `#3b82f6`
- **Purple**: `#8b5cf6`
- **Green**: `#10b981`
- **Orange**: `#f59e0b`
- **Pink**: `#ec4899`

### Theme Implementation
```javascript
// Initialize theme manager
const themeManager = new ThemeManager();

// Set theme mode
themeManager.setThemeMode('dark');

// Set accent color
themeManager.setAccentColor('purple');

// Enable high contrast
themeManager.setHighContrast(true);
```

### Custom Theme Variables
```css
.theme-purple {
  --color-primary: #8b5cf6;
  --color-primary-dark: #7c3aed;
  --gradient-primary: linear-gradient(135deg, #8b5cf6, #7c3aed);
}
```

## Accessibility Guidelines

### Color Contrast
- **Normal text**: Minimum 4.5:1 contrast ratio
- **Large text**: Minimum 3:1 contrast ratio
- **Interactive elements**: Minimum 3:1 contrast ratio

### Keyboard Navigation
```html
<!-- Proper focus indicators -->
<button class="liquid-button" tabindex="0">
  Accessible Button
</button>

<!-- ARIA labels for icon buttons -->
<button class="liquid-button" aria-label="Close dialog">
  <i class="fas fa-times"></i>
</button>
```

### Screen Reader Support
```html
<!-- Descriptive labels -->
<div class="glass-panel-v3" role="region" aria-labelledby="panel-title">
  <h2 id="panel-title">Panel Title</h2>
</div>

<!-- Status announcements -->
<div aria-live="polite" id="status-announcements"></div>
```

### Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
  .animate-glass-slide-in,
  .animate-lift-hover {
    animation: none;
    transition: none;
  }
}
```

## Performance Considerations

### GPU Acceleration
```css
.glass-panel-v3 {
  transform: translateZ(0); /* Force GPU layer */
  will-change: backdrop-filter, transform;
}
```

### Mobile Optimizations
```css
@media (max-width: 768px) {
  .glass-panel-v3 {
    backdrop-filter: blur(8px) saturate(150%); /* Reduced complexity */
  }
}
```

### Animation Performance
```css
/* Prefer transform and opacity for animations */
.animate-lift-hover:hover {
  transform: var(--transform-lift-sm);
  /* Avoid animating layout properties */
}
```

## Browser Support

### Modern Browsers (Full Support)
- Chrome 76+
- Firefox 103+
- Safari 14+
- Edge 79+

### Fallback Support
```css
@supports not (backdrop-filter: blur(10px)) {
  .glass-panel-v3 {
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(0, 0, 0, 0.1);
  }
}
```

## Troubleshooting

### Common Issues

#### Glass Effects Not Visible
**Problem**: Backdrop-filter not working
**Solution**: 
1. Check browser support
2. Ensure element has background color
3. Verify backdrop-filter syntax

```css
/* Correct implementation */
.glass-panel-v3 {
  background: rgba(255, 255, 255, 0.8); /* Required */
  backdrop-filter: blur(10px) saturate(180%);
  -webkit-backdrop-filter: blur(10px) saturate(180%); /* Safari */
}
```

#### Poor Animation Performance
**Problem**: Choppy animations
**Solution**:
1. Use transform and opacity only
2. Add will-change property
3. Enable GPU acceleration

```css
.smooth-animation {
  will-change: transform;
  transform: translateZ(0);
  transition: transform 0.3s ease;
}
```

#### Mobile Performance Issues
**Problem**: Slow performance on mobile
**Solution**:
1. Reduce backdrop-filter complexity
2. Simplify animations
3. Use media queries for mobile-specific styles

```css
@media (max-width: 768px) {
  .glass-panel-v3 {
    backdrop-filter: blur(6px); /* Reduced from 10px */
  }
}
```

### Testing Tools

#### Visual Regression Testing
```javascript
// Run visual tests
vrt.runAllTests();

// Test responsive design
vrt.testResponsiveDesign();
```

#### Performance Testing
```javascript
// Test animation performance
pat.testAnimationPerformance();

// Run accessibility audit
pat.runAccessibilityAudit();
```

## Best Practices

### Component Composition
```html
<!-- Good: Semantic structure with glass styling -->
<article class="glass-panel-v3 animate-glass-slide-in">
  <header class="glass-panel-v3--secondary">
    <h2>Article Title</h2>
  </header>
  <main class="glass-panel-v3--tertiary">
    <p>Article content...</p>
  </main>
</article>
```

### Animation Timing
```css
/* Stagger animations for better UX */
.item:nth-child(1) { animation-delay: 0.1s; }
.item:nth-child(2) { animation-delay: 0.2s; }
.item:nth-child(3) { animation-delay: 0.3s; }
```

### Theme Integration
```javascript
// Listen for theme changes
themeManager.addEventListener('themeChange', (theme) => {
  // Update component state
  updateComponentTheme(theme);
});
```

## Migration Guide

### From Legacy Components
```html
<!-- Old -->
<div class="glass-panel">
  <button class="glass-button">Action</button>
</div>

<!-- New -->
<div class="glass-panel-v3 animate-glass-slide-in">
  <button class="liquid-button liquid-button--primary animate-lift-hover">
    Action
  </button>
</div>
```

### CSS Variable Updates
```css
/* Old variables */
--glass-bg: rgba(255, 255, 255, 0.8);

/* New variables */
--glass-bg-primary: rgba(255, 255, 255, 0.8);
--glass-bg-secondary: rgba(255, 255, 255, 0.6);
--glass-bg-tertiary: rgba(255, 255, 255, 0.4);
```

## Contributing

When adding new components:

1. **Follow naming conventions**: Use BEM methodology
2. **Include accessibility**: Add proper ARIA labels and keyboard support
3. **Test across browsers**: Ensure compatibility and fallbacks
4. **Document usage**: Update this style guide with examples
5. **Performance test**: Verify smooth animations and interactions

## Resources

- [CSS Backdrop Filter MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [CSS Animation Performance](https://web.dev/animations-guide/)
- [Glass Morphism Design Principles](https://uxdesign.cc/glassmorphism-in-user-interfaces-1f39bb1308c9)

---

*This style guide is maintained by the Knowledge Base Agent development team. Last updated: 2024*