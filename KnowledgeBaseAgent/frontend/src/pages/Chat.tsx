import * as React from 'react';
import { useChatStore } from '@/stores';
import { cn } from '@/utils/cn';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PlusIcon, MessageSquareIcon, SendIcon } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/Alert';
import { User, Bot } from 'lucide-react';

function SessionPanel() {
  const { sessions, currentSession, switchSession, createSession, sessionsLoading } = useChatStore();

  React.useEffect(() => {
    createSession('New Chat');
  }, []);

  return (
    <GlassCard className="h-full flex flex-col">
      <div className="flex justify-between items-center p-4 border-b border-glass-border">
        <h3 className="font-semibold text-foreground">Chat Sessions</h3>
        <Button variant="ghost" size="icon" onClick={() => createSession('New Chat')}>
          <PlusIcon className="h-5 w-5" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {sessionsLoading && <LoadingSpinner />}
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => switchSession(session.id)}
            className={cn(
              'w-full text-left flex items-center gap-3 p-2 rounded-md text-sm transition-colors',
              currentSession?.id === session.id
                ? 'bg-primary/20 text-primary-foreground'
                : 'hover:bg-white/10 text-muted-foreground'
            )}
          >
            <MessageSquareIcon className="h-4 w-4" />
            <span className="truncate flex-1">{session.title}</span>
          </button>
        ))}
      </div>
    </GlassCard>
  );
}

function Message({ role, content }: { role: 'user' | 'assistant', content: string }) {
  const Icon = role === 'user' ? User : Bot;
  return (
    <div className={cn("flex items-start gap-4 p-4 rounded-lg", role === 'user' ? '' : 'bg-white/5')}>
      <div className="p-2 rounded-full bg-black/10">
        <Icon className="h-5 w-5 text-foreground" />
      </div>
      <div className="prose prose-invert max-w-none text-foreground pt-1 whitespace-pre-wrap">
        {content}
      </div>
    </div>
  )
}

function ChatInput() {
  const { sendMessage, isTyping } = useChatStore();
  const [input, setInput] = React.useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage(input.trim());
    setInput('');
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 border-t border-glass-border">
      <div className="relative">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your knowledge base..."
          className="pr-12"
          disabled={isTyping}
        />
        <Button type="submit" size="icon" className="absolute top-1/2 right-1 -translate-y-1/2" disabled={isTyping}>
          <SendIcon className="h-5 w-5" />
        </Button>
      </div>
    </form>
  )
}

function ChatPanel() {
  const { messages, isTyping, error, currentSession, messagesLoading } = useChatStore();
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  if (!currentSession) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground">
        Select or create a new chat session to begin.
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messagesLoading && <LoadingSpinner />}
        {messages.map((msg) => (
          <Message key={msg.id} role={msg.role} content={msg.content} />
        ))}
        {isTyping && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Bot className="h-5 w-5 animate-pulse" />
            <span>Assistant is typing...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      {error && (
        <div className="p-4">
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}
      <ChatInput />
    </div>
  );
}

export function Chat() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6 h-[calc(100vh-4rem)]">
      <SessionPanel />
      <GlassCard className="h-full p-0">
        <ChatPanel />
      </GlassCard>
    </div>
  );
}
