import * as React from 'react';
import { useChatStore } from '@/stores';
import { cn } from '@/utils/cn';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { LiquidButton } from '@/components/ui/LiquidButton';
import { GlassInput } from '@/components/ui/GlassInput';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PlusIcon, MessageSquareIcon, SendIcon, User, Bot } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/Alert';

function SessionPanel() {
  const { sessions, currentSession, switchSession, createSession, sessionsLoading } = useChatStore();

  React.useEffect(() => {
    if (sessions.length === 0) {
      createSession('New Chat');
    }
  }, [sessions.length, createSession]);

  return (
    <GlassPanel variant="secondary" className="h-full flex flex-col">
      <div className="flex justify-between items-center p-4 border-b border-glass-border-tertiary">
        <h3 className="font-semibold text-foreground">Chat Sessions</h3>
        <LiquidButton variant="ghost" size="icon" onClick={() => createSession('New Chat')}>
          <PlusIcon className="h-5 w-5" />
        </LiquidButton>
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
                ? 'bg-glass-bg-tertiary text-foreground font-semibold'
                : 'hover:bg-glass-bg-tertiary text-muted-foreground'
            )}
          >
            <MessageSquareIcon className="h-4 w-4 flex-shrink-0" />
            <span className="truncate flex-1">{session.title}</span>
          </button>
        ))}
      </div>
    </GlassPanel>
  );
}

function Message({ role, content }: { role: 'user' | 'assistant', content: string }) {
  const Icon = role === 'user' ? User : Bot;
  return (
    <div className={cn("flex items-start gap-4", role === 'user' ? 'justify-end' : '')}>
      {role === 'assistant' && (
        <div className="p-2 rounded-full bg-glass-bg-secondary">
          <Icon className="h-5 w-5 text-foreground" />
        </div>
      )}
      <div className={cn(
        "max-w-2xl p-4 rounded-xl",
        role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-glass-bg-secondary'
      )}>
        <div className="prose prose-invert max-w-none text-foreground whitespace-pre-wrap">
          {content}
        </div>
      </div>
      {role === 'user' && (
        <div className="p-2 rounded-full bg-glass-bg-secondary">
          <Icon className="h-5 w-5 text-foreground" />
        </div>
      )}
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
    <form onSubmit={handleSubmit} className="p-4">
      <div className="relative">
        <GlassInput
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything..."
          className="pr-12 h-12 text-base"
          disabled={isTyping}
        />
        <LiquidButton type="submit" size="icon" className="absolute top-1/2 right-2 -translate-y-1/2" disabled={isTyping}>
          <SendIcon className="h-5 w-5" />
        </LiquidButton>
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
    <GlassPanel variant="primary" className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messagesLoading && <LoadingSpinner />}
        {messages.map((msg) => (
          <Message key={msg.id} role={msg.role} content={msg.content} />
        ))}
        {isTyping && (
          <div className="flex items-center gap-3 text-muted-foreground">
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
    </GlassPanel>
  );
}

export function Chat() {
  return (
    <div className="flex gap-6 h-full">
      <div className="w-[300px] hidden lg:block">
        <SessionPanel />
      </div>
      <div className="flex-1 h-full">
        <ChatPanel />
      </div>
    </div>
  );
}
