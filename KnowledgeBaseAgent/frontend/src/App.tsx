import { Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/layout/Layout';
import { Dashboard } from '@/pages/Dashboard';
import { KnowledgeBase } from '@/pages/KnowledgeBase';
import { Chat } from '@/pages/Chat';
import { Settings } from '@/pages/Settings';
import { Monitoring } from '@/pages/Monitoring';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

function App() {
  return (
    <ErrorBoundary>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/knowledge" element={<KnowledgeBase />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </ErrorBoundary>
  );
}

export default App;