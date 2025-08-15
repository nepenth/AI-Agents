# Frontend Architecture Documentation

This document provides a comprehensive overview of the design, components, and data flow of the Knowledge Base Agent's frontend application.

## 1. Overview & Tech Stack

The frontend is a modern Single Page Application (SPA) built with the following core technologies:

- **Framework:** React 18 with TypeScript
- **Build Tool:** Vite
- **Styling:** Tailwind CSS
- **State Management:** Zustand
- **Routing:** React Router
- **UI Components:** Radix UI primitives, `lucide-react` for icons

The primary design philosophy is the **"Liquid Glass"** system, a theme-aware and accessible UI that emphasizes translucency, depth, and motion, while providing options for users to reduce effects for clarity.

## 2. Project Structure

The `src` directory is organized by feature and function:

```
src/
├── components/ # Reusable UI components
│   ├── layout/ # Page layout components (Layout, ThemeProvider)
│   └── ui/     # Core component library (Button, GlassCard, etc.)
├── hooks/      # Custom React hooks (e.g., useDebounce)
├── pages/      # Top-level page components for each route
├── services/   # API and WebSocket communication layer
├── stores/     # Zustand state management stores
├── test/       # Test setup and configuration
└── types/      # TypeScript type definitions
```

## 3. Core Concepts

### 3.1. Theming: The "Liquid Glass" System

The UI's appearance is not static; it's a dynamic system controlled by CSS variables.

- **CSS Variables:** The core theme (colors, blur, opacity, shadows) is defined as CSS variables in `src/index.css`. This includes a full set of variables for both light and dark modes.
- **`themeStore`:** A Zustand store (`src/stores/themeStore.ts`) manages user preferences for accessibility:
    - `reduceTransparency`
    - `reduceMotion`
    - `increaseContrast`
  These settings are persisted in the user's `localStorage`.
- **`ThemeProvider`:** A global provider (`src/components/layout/ThemeProvider.tsx`) listens to the `themeStore` and applies the correct `data-*` attributes to the root `<html>` element (e.g., `data-theme-transparency="true"`). The CSS in `index.css` uses these attributes to dynamically change the values of the CSS variables, instantly updating the entire UI's theme.

### 3.2. Component Library

The UI is built from a set of reusable, theme-aware, and accessible components located in `src/components/ui/`. The approach is inspired by `shadcn/ui`:

- **Primitives:** Components are built on top of headless UI primitives from **Radix UI** (`@radix-ui/react-*`). This provides robust accessibility and interaction logic (keyboard navigation, focus management, ARIA attributes) out of the box.
- **Styling:** Components are styled with **Tailwind CSS**.
- **Variants:** Component variants (e.g., button styles, sizes) are managed using **`class-variance-authority` (CVA)**. This allows for a flexible and maintainable API for each component.

**Core Components:**
- `GlassCard`: The main container for UI sections, featuring the dynamic glass effect.
- `Button`: A flexible button with multiple style variants (`default`, `destructive`, `outline`, etc.).
- `Input`, `Select`, `Checkbox`: A complete set of theme-aware form elements.
- `Modal`: A dialog component built on Radix UI's `Dialog` primitive.
- `Tooltip`: A tooltip component built on Radix UI's `Tooltip` primitive.
- `ProgressBar`: A progress bar for indicating loading status, built on Radix UI's `Progress` primitive.
- `Alert`: A component for displaying informational or error messages.

### 3.3. State Management

Global application state is managed with **Zustand**. This provides a simple, unopinionated, and performant state management solution. The stores are organized by domain:

- **`agentStore.ts`:** Manages the state of the AI agent pipeline, including the current task, progress, and system metrics.
- **`knowledgeStore.ts`:** Manages all data related to the knowledge base, including items, categories, search results, and filters.
- **`chatStore.ts`:** Manages chat sessions, messages, and the state of the real-time chat connection (e.g., `isTyping`).
- **`settingsStore.ts`:** Manages the AI model configuration for each pipeline phase.
- **`themeStore.ts`:** Manages the UI's appearance and accessibility settings.

### 3.4. Data Flow

The application follows a standard unidirectional data flow:

1.  **UI Interaction:** A user interacts with a component (e.g., clicks a button).
2.  **Store Action:** The component calls an action in a Zustand store (e.g., `agentStore.startAgent()`).
3.  **API Service:** The store action communicates with the backend via the `apiService` or `websocketService` located in `src/services/`.
4.  **State Update:** Upon receiving a response (or a real-time event via WebSocket), the store updates its state.
5.  **UI Re-render:** React's reactivity ensures that any components subscribed to that piece of state automatically re-render to reflect the new data.

## 4. Application Flow & Page Map

The application's pages are managed by **React Router** in `App.tsx`. Lazy loading is implemented with `React.lazy` and `Suspense` to improve initial page load performance.

- **`App.tsx` (Root):**
  - Wraps the entire application in the `ThemeProvider` and an `ErrorBoundary`.
  - Contains the main `Layout` component (which could include a sidebar and header).
  - Defines all the application routes.

- **`/` -> `Dashboard.tsx`:**
  - The main landing page.
  - **Purpose:** To control and monitor the seven-phase AI agent pipeline.
  - **Features:** Displays the status of each phase (`pending`, `running`, `completed`), shows overall progress with a `ProgressBar`, and provides controls (`Button`s) to start, stop, pause, and resume the agent. It is driven entirely by the `agentStore`.

- **`/knowledge` -> `KnowledgeBase.tsx`:**
  - **Purpose:** To browse, search, and filter all items in the knowledge base.
  - **Features:** A debounced search bar, category filters, and a view-mode toggle (grid/list). It displays a collection of `ItemCard`s.
  - **Navigation:** Each `ItemCard` links to the detail page.

- **`/knowledge/:itemId` -> `KnowledgeItemDetail.tsx`:**
  - **Purpose:** To display a single, richly formatted knowledge item. This is the implementation of the "Dynamic Content Rendering System".
  - **Features:** Fetches a single item's data and renders it in structured `Section`s (e.g., "AI Summary", "Enhanced Content", "Original Content").

- **`/chat` -> `Chat.tsx`:**
  - **Purpose:** To provide a conversational AI interface for querying the knowledge base.
  - **Features:** A two-panel layout with a list of chat sessions on the left and the active conversation on the right. It handles real-time messages, typing indicators, and session management, all powered by the `chatStore`.

- **`/monitoring` -> `Monitoring.tsx`:**
  - **Purpose:** To display live system metrics and logs.
  - **Features:** Shows real-time CPU, memory, and disk usage. It also provides a live-updating view of the backend system logs.

- **`/settings` -> `Settings.tsx`:**
  - **Purpose:** To configure the application.
  - **Features:** A two-part page allowing users to configure the AI models for each pipeline phase and to adjust the UI's appearance and accessibility settings via the `themeStore`.
