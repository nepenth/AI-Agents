# Apple-Style Glassmorphism Design System

This document outlines the comprehensive glassmorphism design system implemented in the AI Agent frontend, inspired by Apple's modern glass design language.

## Overview

Our glassmorphism system creates depth, hierarchy, and visual interest through realistic glass effects including:
- **Backdrop blur** for the signature frosted glass look
- **Translucent backgrounds** with appropriate opacity levels
- **Subtle borders** that enhance glass realism
- **Layered shadows** for depth and dimension
- **Interactive elevation** for engaging user feedback

## Design Philosophy

### Apple-Inspired Principles
1. **Realistic Glass Effects**: Our effects mimic real glass with proper translucency and blur
2. **Surface Hierarchy**: Different glass surfaces for different content importance levels
3. **Subtle Interactions**: Gentle hover and active states that feel natural
4. **Accessibility First**: Respects user preferences for reduced motion and transparency
5. **Performance Optimized**: Efficient CSS implementation for smooth 60fps animations

## CSS Variables System

### Surface Hierarchy

#### Primary Glass Surface
For main content areas and important elements:
```css
--glass-bg-primary: rgba(255, 255, 255, 0.7);           /* Light theme */
--glass-bg-primary: rgba(30, 30, 35, 0.8);              /* Dark theme */
--glass-border-primary: rgba(255, 255, 255, 0.3);       /* Light theme */
--glass-border-primary: rgba(255, 255, 255, 0.15);      /* Dark theme */
--glass-blur-primary: blur(20px);
--glass-shadow-primary: /* Multi-layered realistic shadows */
```

#### Secondary Glass Surface
For secondary content and supporting elements:
```css
--glass-bg-secondary: rgba(255, 255, 255, 0.55);        /* Light theme */
--glass-bg-secondary: rgba(25, 25, 30, 0.7);            /* Dark theme */
--glass-border-secondary: rgba(255, 255, 255, 0.25);    /* Light theme */
--glass-border-secondary: rgba(255, 255, 255, 0.12);    /* Dark theme */
--glass-blur-secondary: blur(16px);
--glass-shadow-secondary: /* Softer shadows for secondary content */
```

#### Tertiary Glass Surface
For subtle backgrounds and minimal emphasis:
```css
--glass-bg-tertiary: rgba(255, 255, 255, 0.4);          /* Light theme */
--glass-bg-tertiary: rgba(20, 20, 25, 0.6);             /* Dark theme */
--glass-border-tertiary: rgba(255, 255, 255, 0.2);      /* Light theme */
--glass-border-tertiary: rgba(255, 255, 255, 0.1);      /* Dark theme */
--glass-blur-tertiary: blur(12px);
--glass-shadow-tertiary: /* Minimal shadows for subtle effects */
```

#### Navigation Glass
For sidebars, headers, and navigation elements:
```css
--glass-bg-navbar: rgba(255, 255, 255, 0.8);            /* Light theme */
--glass-bg-navbar: rgba(15, 15, 20, 0.85);              /* Dark theme */
--glass-border-navbar: rgba(255, 255, 255, 0.4);        /* Light theme */
--glass-border-navbar: rgba(255, 255, 255, 0.18);       /* Dark theme */
--glass-blur-navbar: blur(24px);
--glass-shadow-navbar: /* Strong shadows for navigation clarity */
```

#### Interactive Glass
For buttons and interactive elements:
```css
--glass-bg-interactive: rgba(255, 255, 255, 0.25);      /* Light theme */
--glass-bg-interactive: rgba(40, 45, 55, 0.4);          /* Dark theme */
--glass-border-interactive: rgba(255, 255, 255, 0.4);   /* Light theme */
--glass-border-interactive: rgba(255, 255, 255, 0.15);  /* Dark theme */
--glass-blur-interactive: blur(16px);
--glass-shadow-interactive: /* Interactive shadows with hover states */
```

#### Overlay Glass
For modals, dropdowns, and overlay elements:
```css
--glass-bg-overlay: rgba(255, 255, 255, 0.9);           /* Light theme */
--glass-bg-overlay: rgba(20, 20, 25, 0.9);              /* Dark theme */
--glass-border-overlay: rgba(255, 255, 255, 0.5);       /* Light theme */
--glass-border-overlay: rgba(255, 255, 255, 0.2);       /* Dark theme */
--glass-blur-overlay: blur(40px);
--glass-shadow-overlay: /* Strong shadows for modal prominence */
```

## Component Library

### GlassCard

The main card component with various glass effects:

```tsx
<GlassCard variant="primary" elevated>
  <h3>Primary Glass Card</h3>
  <p>Content with strong glass effect</p>
</GlassCard>

<GlassCard variant="secondary">
  <h3>Secondary Glass Card</h3>
  <p>Content with medium glass effect</p>
</GlassCard>

<GlassCard variant="tertiary">
  <h3>Tertiary Glass Card</h3>
  <p>Content with subtle glass effect</p>
</GlassCard>

<GlassCard variant="interactive" elevated>
  <h3>Interactive Glass Card</h3>
  <p>Clickable card with enhanced hover effects</p>
</GlassCard>
```

**Variants:**
- `primary`: Strong glass effect for main content
- `secondary`: Medium glass effect for supporting content
- `tertiary`: Subtle glass effect for backgrounds
- `interactive`: Enhanced glass effect for clickable elements

**Props:**
- `elevated`: Adds hover lift animation
- `className`: Custom styling override

### GlassPanel

Versatile panel component for different layout sections:

```tsx
<GlassPanel variant="navbar" className="sticky top-0">
  <nav>Navigation content</nav>
</GlassPanel>

<GlassPanel variant="primary" size="lg" elevated>
  <h2>Main Content Panel</h2>
  <p>Important content area</p>
</GlassPanel>

<GlassPanel variant="overlay" className="fixed inset-0">
  <div>Modal content</div>
</GlassPanel>
```

**Variants:**
- `primary`, `secondary`, `tertiary`: Content hierarchy levels
- `navbar`: Optimized for navigation elements
- `interactive`: For clickable panels
- `overlay`: For modals and overlays

**Sizes:**
- `sm`: 12px padding
- `md`: 16px padding (default)
- `lg`: 24px padding
- `xl`: 32px padding

### GlassInput

Input component with glass styling:

```tsx
<GlassInput 
  variant="primary" 
  size="md" 
  placeholder="Enter text..." 
/>

<GlassInput 
  variant="secondary" 
  size="sm" 
  placeholder="Search..." 
/>

<GlassInput 
  variant="tertiary" 
  size="lg" 
  placeholder="Subtle input..." 
/>
```

**Variants:**
- `primary`: Strong glass effect with prominent focus states
- `secondary`: Medium glass effect for secondary inputs
- `tertiary`: Subtle glass effect for minimal designs

**Sizes:**
- `sm`: 32px height
- `md`: 40px height (default)
- `lg`: 48px height

### LiquidButton

Enhanced button component with glass effects:

```tsx
<LiquidButton variant="interactive" size="default" elevated>
  <Play className="h-4 w-4 mr-2" />
  Start Process
</LiquidButton>

<LiquidButton variant="glass" size="lg" elevated>
  <Settings className="h-4 w-4 mr-2" />
  Settings
</LiquidButton>

<LiquidButton variant="outline" size="sm">
  Cancel
</LiquidButton>
```

**Variants:**
- `primary`: Standard glass button
- `secondary`: Subtle glass button
- `interactive`: Enhanced glass with strong hover effects
- `glass`: Legacy glass variant (mapped to interactive)
- `ghost`: Transparent with glass hover
- `outline`: Bordered with glass background on hover

**Sizes:**
- `sm`: Small button (32px height)
- `default`: Standard button (40px height)
- `lg`: Large button (48px height)
- `icon`, `icon-sm`, `icon-lg`: Square icon buttons

**Props:**
- `elevated`: Adds hover lift animation
- `loading`: Shows loading spinner
- `asChild`: Renders as child component (for links)

## Implementation Guidelines

### CSS Structure

All glass effects use this structure:
```css
.glass-element {
  /* Background with transparency */
  background: var(--glass-bg-variant);
  
  /* Border for glass realism */
  border: 1px solid var(--glass-border-variant);
  
  /* Backdrop blur for frosted effect */
  backdrop-filter: var(--glass-blur-variant);
  
  /* Shadows for depth */
  box-shadow: var(--glass-shadow-variant);
  
  /* Subtle gradient overlay */
  position: relative;
  overflow: hidden;
}

.glass-element::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to bottom right, white/opacity, transparent);
  pointer-events: none;
}
```

### Hover States

Interactive elements include these hover effects:
```css
.glass-interactive:hover {
  transform: scale(1.02) translateY(-1px);
  box-shadow: var(--glass-shadow-interactive-hover);
  backdrop-filter: var(--glass-blur-overlay);
}
```

### Accessibility

The system respects user accessibility preferences:

```css
/* Reduced transparency for better readability */
[data-reduce-transparency="true"] {
  --glass-bg-alpha: 1;
  --glass-blur: 0px;
}

/* Reduced motion for accessibility */
@media (prefers-reduced-motion: reduce) {
  .glass-element {
    transition-duration: 0.01ms !important;
    animation: none !important;
  }
}

/* High contrast mode */
[data-increase-contrast="true"] {
  --glass-bg-alpha: 0.85;
  --glass-border-alpha: 0.5;
}
```

## Usage Examples

### Navigation Layout
```tsx
<GlassPanel variant="navbar" className="w-64 h-full">
  <div className="p-6">
    <h1 className="text-xl font-semibold">AI Agent</h1>
  </div>
  <nav className="p-4 space-y-2">
    {navigation.map(item => (
      <NavLink 
        key={item.name}
        className="block p-3 rounded-xl hover:bg-glass-secondary"
      >
        {item.name}
      </NavLink>
    ))}
  </nav>
</GlassPanel>
```

### Header Component
```tsx
<GlassPanel variant="navbar" className="sticky top-0 border-b">
  <div className="flex items-center justify-between p-4">
    <h1 className="text-2xl font-semibold">Dashboard</h1>
    <div className="flex items-center gap-4">
      <GlassInput variant="tertiary" placeholder="Search..." />
      <LiquidButton variant="ghost" size="icon">
        <Bell className="h-4 w-4" />
      </LiquidButton>
    </div>
  </div>
</GlassPanel>
```

### Content Cards
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  <GlassCard variant="primary" elevated>
    <div className="p-6">
      <h3 className="text-lg font-semibold mb-2">Main Feature</h3>
      <p className="text-muted-foreground">Important content area</p>
    </div>
  </GlassCard>
  
  <GlassCard variant="secondary">
    <div className="p-6">
      <h3 className="text-lg font-semibold mb-2">Secondary Feature</h3>
      <p className="text-muted-foreground">Supporting content</p>
    </div>
  </GlassCard>
  
  <GlassCard variant="tertiary">
    <div className="p-6">
      <h3 className="text-lg font-semibold mb-2">Additional Info</h3>
      <p className="text-muted-foreground">Subtle background content</p>
    </div>
  </GlassCard>
</div>
```

### Interactive Elements
```tsx
<div className="flex gap-4">
  <LiquidButton variant="interactive" size="lg" elevated>
    <Play className="h-5 w-5 mr-2" />
    Start New Run
  </LiquidButton>
  
  <LiquidButton variant="outline" size="lg">
    <Square className="h-5 w-5 mr-2" />
    Stop
  </LiquidButton>
  
  <LiquidButton variant="ghost" size="lg">
    <Settings className="h-5 w-5 mr-2" />
    Settings
  </LiquidButton>
</div>
```

## Performance Considerations

### Efficient CSS
- Use CSS custom properties for consistent theming
- Minimize the number of backdrop-filter layers
- Combine multiple shadow effects into single declarations
- Use `transform: translateZ(0)` for hardware acceleration when needed

### Responsive Design
- Reduce glass effects on mobile for better performance
- Use `touch-manipulation` for better touch responsiveness
- Adjust blur values for different screen sizes

### Browser Support
- Backdrop-filter has good modern browser support
- Provide fallbacks for older browsers:
```css
.glass-element {
  background: var(--glass-bg-fallback); /* Solid fallback */
  backdrop-filter: var(--glass-blur);
}

@supports not (backdrop-filter: blur()) {
  .glass-element {
    background: var(--glass-bg-solid);
  }
}
```

## Best Practices

### When to Use Glass Effects
✅ **Good for:**
- Navigation elements
- Content cards
- Modal overlays
- Interactive buttons
- Panel layouts

❌ **Avoid for:**
- Text-heavy content areas
- Form inputs with poor contrast
- Frequently updated content (performance)
- Critical accessibility content

### Design Guidelines
1. **Maintain Hierarchy**: Use stronger glass effects for more important content
2. **Consider Context**: Strong blur works well over colorful backgrounds
3. **Test Accessibility**: Always verify readability with reduced transparency
4. **Performance**: Limit nested glass elements
5. **Consistency**: Use the defined variants rather than custom values

### Development Tips
1. Always use the CSS custom properties rather than hardcoded values
2. Test glass effects in both light and dark themes
3. Verify accessibility with reduced motion and transparency settings
4. Use the provided component variants for consistency
5. Add `relative z-10` to content inside glass containers for proper layering

## Future Enhancements

### Planned Improvements
- [ ] Additional surface variants for specific use cases
- [ ] Enhanced animation presets for glass interactions
- [ ] Better mobile-optimized glass effects
- [ ] Extended color theme support
- [ ] Performance optimizations for complex layouts

### Customization Options
- [ ] User-configurable glass intensity
- [ ] Dynamic blur based on scroll position
- [ ] Contextual glass effects based on background content
- [ ] Enhanced dark mode glass variations

This glassmorphism design system provides a solid foundation for creating beautiful, accessible, and performant glass effects throughout the AI Agent application while maintaining consistency with Apple's design language.