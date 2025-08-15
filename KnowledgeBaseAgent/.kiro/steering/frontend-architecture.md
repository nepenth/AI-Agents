# Frontend Architecture Guidelines

This document provides steering guidelines for the AI Agent Frontend system architecture and implementation patterns.

## System Overview

The AI Agent Frontend is built as a modern React Single Page Application (SPA) focused on Twitter/X bookmark processing visualization with the following core principles:

- **Seven-Phase Pipeline Visualization**: Real-time monitoring and control of the backend seven-phase processing pipeline
- **Twitter/X-First Design**: Specialized UI components for displaying Twitter/X content, threads, and media analysis
- **Liquid Glass Design System**: Theme-aware and accessible UI emphasizing translucency, depth, and motion
- **Real-time Communication**: WebSocket integration for live pipeline progress and system metrics
- **AI Model Management**: Comprehensive interface for configuring and testing AI models across all phases
- **Knowledge Base Integration**: Rich content browsing and search capabilities with vector similarity
- **Mobile-First Responsive**: Fully responsive design optimized for all device sizes

## Technology Stack

### Core Technologies
- **Framework**: React 18 with TypeScript for type safety and modern React features
- **Build Tool**: Vite for fast development and optimized production builds
- **Styling**: Tailwind CSS for utility-first styling with custom design system
- **State Management**: Zustand for simple, performant global state management
- **Routing**: React Router for client-side routing with lazy loading
- **UI Components**: Radix UI primitives for accessible, headless components

### Additional Libraries
- **Icons**: Lucide React for consistent iconography
- **Animations**: CSS transitions and transforms with reduced motion support
- **Testing**: Vitest and React Testing Library for comprehensive testing
- **Type Safety**: Strict TypeScript configuration with comprehensive type definitions

## Architecture Layers

### 1. Component Architecture (`src/components/`)

#### UI Component Library (`src/components/ui/`)
Reusable, theme-aware, and accessible components following shadcn/ui patterns:

**Implementation Pattern:**
```typescript
// Component with variants using class-variance-authority
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/utils/cn'

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input hover:bg-accent hover:text-accent-foreground",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
```

**Core Components:**
- `GlassCard`: Main container with dynamic glass effect and theme awareness
- `Button`: Flexible button with multiple variants and accessibility features
- `ProgressBar`: Animated progress indicators for pipeline phases
- `StatusBadge`: Phase status visualization with color coding
- `WebSocketIndicator`: Real-time connection status display
- `Modal`: Accessible dialog components built on Radix UI primitives
- `Tooltip`: Context-sensitive help and information display

#### Feature Components
Domain-specific components organized by feature area:

**Pipeline Components (`src/components/pipeline/`):**
- `PipelineDashboard`: Main pipeline control and monitoring interface
- `PhaseCard`: Individual phase status and control component
- `ProgressIndicator`: Real-time progress visualization
- `ProcessingStats`: Performance metrics and statistics display
- `RealTimeMetrics`: Live system metrics with WebSocket updates

**AI Model Components (`src/components/ai-models/`):**
- `ModelConfiguration`: Phase-specific model configuration interface
- `ModelSelector`: Available model discovery and selection
- `ModelTester`: Connectivity and capability testing
- `ModelStatus`: Real-time model availability and performance
- `ModelBenchmark`: Performance testing and comparison tools

**Knowledge Base Components (`src/components/knowledge/`):**
- `KnowledgeBrowser`: Main content browsing interface
- `SearchInterface`: Advanced search with vector similarity
- `ContentViewer`: Rich content display with media analysis
- `CategoryExplorer`: AI-generated category navigation
- `KnowledgeItemCard`: Individual content item display

**Twitter/X Processing Components (`src/components/tweet-processing/`):**
- `TweetInput`: Tweet ID validation and input interface
- `TweetDisplay`: Fetched Twitter data visualization
- `ProcessingResults`: AI analysis results display
- `ComparisonView`: AI vs simulated results comparison
- `MediaAnalysisVisualization`: Vision model results display
- `ContentUnderstandingDisplay`: Detailed AI insights presentation

### 2. State Management (`src/stores/`)

Global application state using Zustand with domain-specific stores:

**Implementation Pattern:**
```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AgentState {
  // State properties
  currentPhase: number | null
  isRunning: boolean
  progress: Record<number, number>
  
  // Actions
  startAgent: () => Promise<void>
  stopAgent: () => Promise<void>
  updateProgress: (phase: number, progress: number) => void
}

export const useAgentStore = create<AgentState>()(
  persist(
    (set, get) => ({
      // Initial state
      currentPhase: null,
      isRunning: false,
      progress: {},
      
      // Actions
      startAgent: async () => {
        set({ isRunning: true })
        // API call logic
      },
      
      stopAgent: async () => {
        set({ isRunning: false, currentPhase: null })
        // API call logic
      },
      
      updateProgress: (phase, progress) => {
        set(state => ({
          progress: { ...state.progress, [phase]: progress }
        }))
      },
    }),
    {
      name: 'agent-store',
      partialize: (state) => ({ progress: state.progress }),
    }
  )
)
```

**Store Organization:**
- `agentStore`: Pipeline state, progress tracking, and control actions
- `knowledgeStore`: Content data, search results, and filtering state
- `chatStore`: Chat sessions, messages, and real-time connection state
- `settingsStore`: AI model configuration and system settings
- `themeStore`: UI appearance and accessibility preferences

### 3. Service Layer (`src/services/`)

API communication and external service integration:

**Implementation Pattern:**
```typescript
class PipelineService {
  private baseUrl = '/api/v1/pipeline'
  
  async executePhase(phase: number, config?: any): Promise<TaskResponse> {
    const response = await fetch(`${this.baseUrl}/phases/${phase}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config || {}),
    })
    
    if (!response.ok) {
      throw new Error(`Failed to execute phase ${phase}`)
    }
    
    return response.json()
  }
  
  async getStatus(): Promise<PipelineStatus> {
    const response = await fetch(`${this.baseUrl}/status`)
    return response.json()
  }
}

export const pipelineService = new PipelineService()
```

**Service Organization:**
- `pipelineService`: Seven-phase pipeline control and monitoring
- `aiModelService`: Model configuration, testing, and validation
- `knowledgeService`: Content browsing, search, and filtering
- `tweetService`: Twitter/X API integration and processing
- `websocketService`: Real-time communication and event handling

### 4. Hook System (`src/hooks/`)

Custom React hooks for reusable logic:

**Implementation Pattern:**
```typescript
export function useRealTimeUpdates<T>(
  eventType: string,
  initialData: T
): T {
  const [data, setData] = useState<T>(initialData)
  const { isConnected, subscribe } = useWebSocket()
  
  useEffect(() => {
    if (!isConnected) return
    
    const unsubscribe = subscribe(eventType, (newData: T) => {
      setData(newData)
    })
    
    return unsubscribe
  }, [eventType, isConnected, subscribe])
  
  return data
}
```

**Hook Categories:**
- `useWebSocket`: WebSocket connection management with auto-reconnection
- `useRealTimeUpdates`: Real-time data synchronization
- `useApi`: API request management with error handling and caching
- `useDebounce`: Input debouncing for search and filtering
- `usePagination`: Pagination logic for large datasets
- `useLocalStorage`: Persistent local storage with type safety

## Design System: Liquid Glass

### 1. Theme Architecture

Dynamic theming system using CSS variables and data attributes:

**CSS Variable Structure:**
```css
:root {
  /* Base colors */
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  
  /* Glass effect variables */
  --glass-opacity: 0.8;
  --glass-blur: 12px;
  --glass-border: 1px;
  
  /* Animation variables */
  --transition-duration: 200ms;
  --animation-scale: 1;
}

[data-theme="dark"] {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
}

[data-reduce-transparency="true"] {
  --glass-opacity: 1;
  --glass-blur: 0px;
}

[data-reduce-motion="true"] {
  --transition-duration: 0ms;
  --animation-scale: 0;
}
```

**Theme Provider Implementation:**
```typescript
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { theme, reduceTransparency, reduceMotion, increaseContrast } = useThemeStore()
  
  useEffect(() => {
    const root = document.documentElement
    
    root.setAttribute('data-theme', theme)
    root.setAttribute('data-reduce-transparency', reduceTransparency.toString())
    root.setAttribute('data-reduce-motion', reduceMotion.toString())
    root.setAttribute('data-increase-contrast', increaseContrast.toString())
  }, [theme, reduceTransparency, reduceMotion, increaseContrast])
  
  return <>{children}</>
}
```

### 2. Accessibility Features

Comprehensive accessibility support following WCAG 2.1 AA guidelines:

**Accessibility Implementation:**
- **Keyboard Navigation**: Full keyboard support with visible focus indicators
- **Screen Reader Support**: Proper ARIA labels and semantic HTML structure
- **Motion Preferences**: Respect for `prefers-reduced-motion` system setting
- **Contrast Options**: High contrast mode for improved visibility
- **Transparency Control**: Option to reduce transparency for clarity
- **Focus Management**: Proper focus trapping in modals and complex components

### 3. Responsive Design

Mobile-first responsive design with breakpoint system:

**Breakpoint System:**
```typescript
const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
}

// Usage in Tailwind classes
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
```

**Responsive Patterns:**
- **Mobile Navigation**: Collapsible sidebar with touch-friendly controls
- **Adaptive Layouts**: Grid systems that adapt to screen size
- **Touch Optimization**: Larger touch targets and gesture support
- **Performance Optimization**: Lazy loading and code splitting for mobile

## Real-time Communication

### 1. WebSocket Integration

Robust WebSocket connection management with automatic reconnection:

**WebSocket Service Pattern:**
```typescript
class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url)
      
      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        resolve()
      }
      
      this.ws.onclose = () => {
        this.handleReconnection()
      }
      
      this.ws.onerror = (error) => {
        reject(error)
      }
      
      this.ws.onmessage = (event) => {
        this.handleMessage(JSON.parse(event.data))
      }
    })
  }
  
  private handleReconnection(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      setTimeout(() => {
        this.reconnectAttempts++
        this.connect()
      }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts))
    }
  }
}
```

### 2. Event Handling

Structured event handling for different types of real-time updates:

**Event Types:**
- `pipeline.phase.started`: Phase execution started
- `pipeline.phase.progress`: Phase progress updates
- `pipeline.phase.completed`: Phase execution completed
- `system.metrics.updated`: System performance metrics
- `model.status.changed`: AI model availability changes
- `content.processed`: New content processing completed

## Performance Optimization

### 1. Code Splitting and Lazy Loading

Optimize bundle size and initial load performance:

**Route-based Code Splitting:**
```typescript
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const KnowledgeBase = lazy(() => import('@/pages/KnowledgeBase'))
const Settings = lazy(() => import('@/pages/Settings'))

function App() {
  return (
    <Router>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/knowledge" element={<KnowledgeBase />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Suspense>
    </Router>
  )
}
```

### 2. State Optimization

Efficient state management to prevent unnecessary re-renders:

**Selective State Subscriptions:**
```typescript
// Only subscribe to specific state slices
const isRunning = useAgentStore(state => state.isRunning)
const currentPhase = useAgentStore(state => state.currentPhase)

// Use shallow comparison for object state
const progress = useAgentStore(state => state.progress, shallow)
```

### 3. Virtual Scrolling

Handle large datasets efficiently:

**Virtual Scrolling Implementation:**
```typescript
function VirtualizedList({ items }: { items: any[] }) {
  const [visibleRange, setVisibleRange] = useState({ start: 0, end: 50 })
  
  const visibleItems = useMemo(() => 
    items.slice(visibleRange.start, visibleRange.end),
    [items, visibleRange]
  )
  
  return (
    <div className="virtual-list" onScroll={handleScroll}>
      {visibleItems.map(item => (
        <ItemComponent key={item.id} item={item} />
      ))}
    </div>
  )
}
```

## Testing Strategy

### 1. Component Testing

Comprehensive testing for all UI components:

**Testing Pattern:**
```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import { Button } from '@/components/ui/Button'

describe('Button', () => {
  it('renders with correct variant styles', () => {
    render(<Button variant="destructive">Delete</Button>)
    
    const button = screen.getByRole('button', { name: /delete/i })
    expect(button).toHaveClass('bg-destructive')
  })
  
  it('handles click events', () => {
    const handleClick = vi.fn()
    render(<Button onClick={handleClick}>Click me</Button>)
    
    fireEvent.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })
})
```

### 2. Integration Testing

Test component interactions and data flow:

**Integration Test Pattern:**
```typescript
describe('Pipeline Dashboard Integration', () => {
  it('starts pipeline and updates progress', async () => {
    render(<PipelineDashboard />)
    
    const startButton = screen.getByRole('button', { name: /start pipeline/i })
    fireEvent.click(startButton)
    
    await waitFor(() => {
      expect(screen.getByText(/phase 1 running/i)).toBeInTheDocument()
    })
  })
})
```

### 3. Accessibility Testing

Ensure WCAG compliance and screen reader compatibility:

**Accessibility Test Pattern:**
```typescript
import { axe, toHaveNoViolations } from 'jest-axe'

expect.extend(toHaveNoViolations)

describe('Accessibility', () => {
  it('has no accessibility violations', async () => {
    const { container } = render(<Dashboard />)
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
```

## Deployment and Build

### 1. Build Configuration

Optimized Vite configuration for production:

**Vite Config:**
```typescript
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          ui: ['@radix-ui/react-dialog', '@radix-ui/react-tooltip'],
          charts: ['recharts', 'd3'],
        },
      },
    },
    chunkSizeWarningLimit: 1000,
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'zustand'],
  },
})
```

### 2. Environment Configuration

Environment-specific configuration management:

**Environment Variables:**
```typescript
interface Config {
  apiUrl: string
  wsUrl: string
  environment: 'development' | 'staging' | 'production'
}

export const config: Config = {
  apiUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws',
  environment: import.meta.env.MODE as Config['environment'],
}
```

This frontend architecture provides a robust, scalable, and maintainable foundation for the AI Agent Dashboard while ensuring excellent user experience, accessibility, and performance.