import * as React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/layout/Layout';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { ThemeProvider } from './components/layout/ThemeProvider';
import { LoadingSpinner } from './components/ui/LoadingSpinner';
import { AccessibilityProvider } from '@/contexts/AccessibilityContext';
import { SkipLinks } from '@/components/accessibility/SkipLinks';

const Dashboard = React.lazy(() => import('@/pages/Dashboard').then(m => ({ default: m.Dashboard })));
const KnowledgeBase = React.lazy(() => import('@/pages/KnowledgeBase').then(m => ({ default: m.KnowledgeBase })));
const KnowledgeItemDetail = React.lazy(() => import('@/pages/KnowledgeItemDetail').then(m => ({ default: m.KnowledgeItemDetail })));
const Chat = React.lazy(() => import('@/pages/Chat').then(m => ({ default: m.Chat })));
const Settings = React.lazy(() => import('@/pages/Settings').then(m => ({ default: m.Settings })));
const Monitoring = React.lazy(() => import('@/pages/Monitoring').then(m => ({ default: m.Monitoring })));


function App() {
  return (
    <AccessibilityProvider>
      <ThemeProvider>
        <ErrorBoundary>
          <SkipLinks />
          <Layout>
            <main id="main-content" tabIndex={-1}>
              <React.Suspense 
                fallback={
                  <div 
                    className="flex h-full w-full items-center justify-center"
                    role="status"
                    aria-label="Loading page content"
                  >
                    <LoadingSpinner />
                    <span className="sr-only">Loading...</span>
                  </div>
                }
              >
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/knowledge" element={<KnowledgeBase />} />
                  <Route path="/knowledge/:itemId" element={<KnowledgeItemDetail />} />
                  <Route path="/chat" element={<Chat />} />
                  <Route path="/monitoring" element={<Monitoring />} />
                  <Route path="/settings" element={<Settings />} />
                </Routes>
              </React.Suspense>
            </main>
          </Layout>
        </ErrorBoundary>
      </ThemeProvider>
    </AccessibilityProvider>
  );
}

export default App;