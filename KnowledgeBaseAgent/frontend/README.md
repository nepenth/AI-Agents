# AI Agent Frontend

Modern React frontend application for the AI Agent Knowledge Base system.

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for styling with custom design system
- **React Router** for client-side routing
- **Zustand** for state management (to be implemented in next task)
- **Headless UI** for accessible UI components
- **Heroicons** for icons
- **Vitest** for testing

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
├── components/          # Reusable UI components
│   ├── ui/             # Basic UI components (Button, Input, etc.)
│   ├── layout/         # Layout components (Header, Sidebar, etc.)
│   └── __tests__/      # Component tests
├── pages/              # Page components
│   ├── Dashboard.tsx
│   ├── KnowledgeBase.tsx
│   ├── Chat.tsx
│   ├── Settings.tsx
│   ├── Monitoring.tsx
│   └── __tests__/      # Page tests
├── hooks/              # Custom React hooks (to be implemented)
├── services/           # API and WebSocket services (to be implemented)
├── stores/             # Zustand stores (to be implemented)
├── types/              # TypeScript type definitions
├── utils/              # Utility functions
├── test/               # Test setup and utilities
└── styles/             # Global styles
```

## Features Implemented

### Task 13: Frontend Project Foundation ✅

- [x] React project with TypeScript using Vite
- [x] Tailwind CSS with custom design system
- [x] Development environment with hot reload and proxy
- [x] React Router with protected route patterns
- [x] ESLint, Prettier, and TypeScript configuration
- [x] Basic component tests with Vitest and React Testing Library

### Current Status

The frontend foundation is complete with:

- Modern development environment setup
- Responsive layout with sidebar navigation
- Basic dashboard with system metrics display
- Placeholder pages for all main features
- Component library foundation
- Testing infrastructure
- Code quality tools (ESLint, Prettier)

### Task 14: State Management and API Integration ✅

- [x] Zustand stores for agent, knowledge base, and chat state management
- [x] API service layer with TypeScript interfaces and error handling
- [x] HTTP client with request/response interceptors and retry logic
- [x] WebSocket service with reconnection and event handling
- [x] Custom React hooks for API data fetching and state synchronization
- [x] Comprehensive tests for state management and API integration

### Current Status

The frontend now includes:

- **Complete API Integration**: RESTful API client with error handling, authentication, and retry logic
- **WebSocket Support**: Real-time communication with automatic reconnection
- **State Management**: Zustand stores for agent control, knowledge base, and chat functionality
- **Custom Hooks**: Reusable hooks for API calls, WebSocket events, pagination, and local storage
- **Comprehensive Testing**: Unit tests for services, hooks, and stores
- **TypeScript Support**: Full type safety across all API interactions and state management

### Next Steps (Task 15)

- Create reusable UI components using Headless UI and Tailwind CSS
- Implement responsive layout components with mobile-first design
- Add form components with validation and error handling
- Create data visualization components for charts and progress indicators
- Implement loading states, error boundaries, and fallback components

## Development Guidelines

### Code Style

- Use TypeScript for all components and utilities
- Follow React best practices and hooks patterns
- Use Tailwind CSS utility classes for styling
- Implement responsive design mobile-first
- Write tests for all components and utilities

### Component Guidelines

- Use functional components with hooks
- Implement proper TypeScript interfaces
- Use forwardRef for components that need ref access
- Follow accessibility best practices
- Use semantic HTML elements

### Testing

- Write unit tests for all components
- Test user interactions and edge cases
- Mock external dependencies
- Maintain high test coverage
- Use React Testing Library best practices

## API Integration

The frontend is configured to proxy API requests to the backend:

- API requests to `/api/*` are proxied to `http://localhost:8000`
- WebSocket connections to `/ws/*` are proxied to `ws://localhost:8000`

## Build and Deployment

The application builds to static files that can be served from any web server:

```bash
npm run build
```

Output is generated in the `dist/` directory with:
- Optimized JavaScript bundles with code splitting
- CSS with Tailwind optimizations
- Static assets with proper caching headers
- Source maps for debugging