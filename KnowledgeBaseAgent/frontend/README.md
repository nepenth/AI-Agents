# AI Agent Frontend Dashboard

Modern React frontend application for the AI Agent Knowledge Base system with comprehensive Twitter/X bookmark processing visualization.

## Tech Stack

- **React 18** with TypeScript for modern component development
- **Vite** for fast development and optimized production builds
- **Tailwind CSS** with Liquid Glass design system
- **Zustand** for lightweight state management
- **React Router** for client-side routing with lazy loading
- **Radix UI** for accessible headless components
- **Lucide React** for consistent iconography
- **Recharts** for data visualization and analytics
- **Vitest** and React Testing Library for comprehensive testing

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage

# Lint code
npm run lint
```

## Project Structure

```
src/
├── components/              # Feature-organized components
│   ├── ui/                 # Core UI component library
│   ├── layout/             # Layout and navigation components
│   ├── pipeline/           # Seven-phase pipeline components
│   ├── ai-models/          # AI model configuration components
│   ├── knowledge/          # Knowledge base and search components
│   ├── tweet-processing/   # Twitter/X processing components
│   ├── monitoring/         # System monitoring and analytics
│   └── __tests__/          # Component tests
├── pages/                  # Top-level page components
│   ├── Dashboard.tsx       # Pipeline control dashboard
│   ├── KnowledgeBase.tsx   # Content browsing and search
│   ├── Chat.tsx           # AI chat interface
│   ├── Settings.tsx       # System configuration
│   ├── Monitoring.tsx     # System monitoring
│   └── __tests__/         # Page tests
├── hooks/                  # Custom React hooks
│   ├── useWebSocket.ts     # WebSocket connection management
│   ├── useRealTimeUpdates.ts # Real-time data synchronization
│   ├── useApi.ts          # API request management
│   ├── useDebounce.ts     # Input debouncing
│   └── usePagination.ts   # Pagination logic
├── services/               # API and external service integration
│   ├── api.ts             # Core API client
│   ├── websocket.ts       # WebSocket service
│   ├── pipelineService.ts # Pipeline control API
│   ├── aiModelService.ts  # AI model management API
│   ├── knowledgeService.ts # Knowledge base API
│   └── tweetService.ts    # Twitter/X integration API
├── stores/                 # Zustand state management
│   ├── agentStore.ts      # Pipeline state and control
│   ├── knowledgeStore.ts  # Knowledge base and search state
│   ├── chatStore.ts       # Chat sessions and messages
│   └── themeStore.ts      # UI theme and accessibility
├── types/                  # TypeScript type definitions
├── utils/                  # Utility functions
└── test/                   # Test setup and utilities
```

## Features Implemented

### ✅ Core Infrastructure (Tasks 1-3)
- **Enhanced UI Component Library**: Complete set of accessible components with Liquid Glass design
- **WebSocket Connection Management**: Real-time updates with automatic reconnection
- **API Service Layer**: Comprehensive backend integration with error handling and retry logic

### ✅ Pipeline Visualization (Tasks 4-6)
- **Pipeline Dashboard**: Seven-phase pipeline control and monitoring
- **Real-time Processing Visualization**: Live progress tracking with WebSocket integration
- **Tweet Processing Interface**: Twitter/X content analysis and comparison tools

### ✅ AI Model Management (Tasks 7-8)
- **Model Configuration Interface**: Phase-specific AI model setup and testing
- **Model Testing and Validation**: Connectivity testing and performance benchmarking

### ✅ Knowledge Base (Tasks 9-10)
- **Knowledge Base Browser**: Content browsing with category navigation
- **Advanced Search and Filtering**: Vector similarity, hybrid search, and comprehensive filtering

### ✅ System Monitoring (Tasks 11-12)
- **System Monitoring Dashboard**: Real-time system health with multi-GPU support
- **Performance Monitoring and Analytics**: AI model performance tracking and alerting

## Key Features

### Seven-Phase Pipeline Visualization
- Real-time monitoring of all pipeline phases
- Sub-phase tracking (bookmark caching, media analysis, content understanding, categorization)
- Progress indicators with WebSocket updates
- Error handling and recovery options

### Advanced Search Capabilities
- **Vector Similarity Search**: AI-powered semantic search
- **Hybrid Search**: Combined text and vector search
- **Advanced Filtering**: 15+ filter types including date, engagement, media, threads
- **Saved Searches**: Save and manage frequently used searches
- **Search Analytics**: Performance metrics and result ranking

### AI Model Management
- **Multi-Provider Support**: Ollama, LocalAI, OpenAI-compatible models
- **Phase-Specific Configuration**: Different models for vision, generation, synthesis, chat, embeddings
- **Real-time Testing**: Connectivity and capability validation
- **Performance Monitoring**: Response times, error rates, and throughput tracking

### System Monitoring Excellence
- **Multi-GPU Support**: Individual NVIDIA GPU monitoring with temperature in Fahrenheit
- **Real-time Metrics**: CPU, memory, disk, network, and GPU utilization
- **Performance Analytics**: Historical data with interactive charts
- **Intelligent Alerting**: Configurable thresholds with multiple severity levels
- **Diagnostic Tools**: Automated system health testing

### Twitter/X Processing
- **Thread Detection**: Automatic thread identification and collective analysis
- **Media Analysis**: Vision model integration for image and video content
- **Engagement Tracking**: Real-time metrics for likes, retweets, replies, quotes
- **Content Understanding**: AI-powered content analysis and categorization

## Design System: Liquid Glass

### Theme Features
- **Dynamic Theming**: CSS variables with light/dark mode support
- **Accessibility Options**: Reduced transparency, motion, and high contrast modes
- **Glass Effects**: Translucent containers with blur and depth
- **Responsive Design**: Mobile-first with touch-optimized interactions

### Accessibility Compliance
- **WCAG 2.1 AA**: Full compliance with accessibility standards
- **Keyboard Navigation**: Complete keyboard support with focus indicators
- **Screen Reader Support**: Proper ARIA labels and semantic HTML
- **Motion Preferences**: Respects user's reduced motion settings

## Real-time Communication

### WebSocket Integration
- **Automatic Reconnection**: Robust connection management with exponential backoff
- **Event Handling**: Structured event system for different update types
- **Connection Status**: Visual indicators for connection health
- **Message Queuing**: Reliable message delivery with offline support

### Event Types
- `pipeline.phase.started/progress/completed`: Pipeline execution updates
- `system.metrics.updated`: Real-time system performance data
- `model.status.changed`: AI model availability changes
- `content.processed`: New content processing notifications

## Performance Optimization

### Code Splitting
- **Route-based Splitting**: Lazy loading for all major pages
- **Component Splitting**: Dynamic imports for heavy components
- **Bundle Optimization**: Separate chunks for vendor, UI, and chart libraries

### State Management
- **Selective Subscriptions**: Only subscribe to needed state slices
- **Shallow Comparisons**: Efficient object state updates
- **Persistent Storage**: Critical state persisted in localStorage

### Data Handling
- **Virtual Scrolling**: Efficient rendering of large datasets
- **Debounced Search**: Optimized search input handling
- **Caching Strategies**: API response caching with invalidation

## API Integration

The frontend integrates with the seven-phase pipeline backend:

- **Pipeline Control**: `/api/v1/pipeline/*` - Phase execution and monitoring
- **AI Models**: `/api/v1/system/models/*` - Model configuration and testing
- **Knowledge Base**: `/api/v1/knowledge/*` - Content search and browsing
- **Twitter/X Integration**: `/api/v1/content/twitter/*` - Bookmark processing
- **System Monitoring**: `/api/v1/system/*` - Health and performance metrics
- **WebSocket**: `/ws` - Real-time updates and notifications

## Development Guidelines

### Component Development
- Use functional components with TypeScript
- Build on Radix UI primitives for accessibility
- Follow Liquid Glass design system patterns
- Implement proper error boundaries and loading states

### State Management
- Use Zustand for global state with domain-specific stores
- Implement optimistic updates for better UX
- Handle loading and error states consistently
- Persist critical state in localStorage

### Testing Strategy
- Unit tests for all components and hooks
- Integration tests for API services and WebSocket connections
- End-to-end tests for complete user workflows
- Accessibility testing with axe-core

### Performance Best Practices
- Lazy load routes and heavy components
- Use React.memo for expensive components
- Implement virtual scrolling for large lists
- Optimize bundle size with code splitting

## Build and Deployment

### Production Build
```bash
npm run build
```

### Build Optimization
- **Tree Shaking**: Removes unused code
- **Minification**: Compressed JavaScript and CSS
- **Asset Optimization**: Optimized images and fonts
- **Caching**: Proper cache headers for static assets

### Environment Configuration
- Development: Hot reload with API proxy
- Staging: Production build with staging API
- Production: Optimized build with CDN integration

This frontend provides a comprehensive, accessible, and performant interface for managing and monitoring the AI Agent's seven-phase Twitter/X bookmark processing pipeline.