import { GlassCard } from '@/components/ui/GlassCard';
import { useChatStore } from '@/stores/chatStore';
import { useEffect } from 'react';

export function Chat() {
  const { messages, loadHistory } = useChatStore();

  useEffect(() => {
    // Load empty or existing history; no stubs
    loadHistory?.().catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-gray-900">Chat</h2>
        <p className="text-sm text-gray-600">Chat with your AI assistant about your knowledge base</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <GlassCard title="Conversation">
            {messages && messages.length > 0 ? (
              <div className="space-y-2 text-sm text-gray-800">
                {messages.map((m) => (
                  <div key={m.id} className="whitespace-pre-wrap">
                    <span className="font-medium">{m.role}: </span>
                    {m.content}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-600">No messages yet.</div>
            )}
          </GlassCard>
          <GlassCard>
            <div className="flex gap-3">
              <input className="input flex-1" placeholder="Type your message..." />
              <button className="btn-primary px-4">Send</button>
            </div>
          </GlassCard>
        </div>
        <div className="space-y-6">
          <GlassCard title="Model & Context">
            <div className="space-y-3">
              <select className="input">
                <option>Default (chat)</option>
              </select>
              <div className="text-xs text-gray-600">Adjust model for this session.</div>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}