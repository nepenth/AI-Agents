import { GlassCard } from '@/components/ui/GlassCard';
import { useKnowledgeStore } from '@/stores';
import { useEffect } from 'react';

export function KnowledgeBase() {
  const { knowledgeItems, loadKnowledgeItems, knowledgeItemsLoading } = useKnowledgeStore();

  useEffect(() => {
    loadKnowledgeItems().catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-gray-900">Knowledge Base</h2>
        <p className="text-sm text-gray-600">Browse and manage your knowledge base items</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlassCard title="Filters">
          <div className="space-y-3">
            <input className="input" placeholder="Search..." />
            <select className="input">
              <option>All Categories</option>
            </select>
          </div>
        </GlassCard>
        <div className="lg:col-span-2 space-y-6">
          <GlassCard title="Results">
            {knowledgeItemsLoading ? (
              <div className="text-sm text-gray-600">Loading...</div>
            ) : knowledgeItems.length === 0 ? (
              <div className="text-sm text-gray-600">No items yet.</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {knowledgeItems.map(item => (
                  <div key={item.id} className="card p-4">
                    <div className="text-sm font-medium text-gray-900">{item.title || item.id}</div>
                    <div className="text-sm text-gray-600">{item.summary || 'No summary'}</div>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  );
}