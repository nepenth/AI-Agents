import * as React from 'react';
import { useChatStore } from '@/stores';
import { cn } from '@/utils/cn';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { LiquidButton } from '@/components/ui/LiquidButton';
import { GlassInput } from '@/components/ui/GlassInput';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PlusIcon, MessageSquareIcon, SendIcon, User, Bot, Sparkles, FileText, Search } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/Alert';

function SessionPanel() {
  const { sessions, currentSession, switchSession, createSession, sessionsLoading } = useChatStore();

  React.useEffect(() => {
    if (sessions.length === 0) {
      createSession('New Chat');
    }
  }, [sessions.length, createSession]);

  return (
    <GlassPanel variant="secondary" className="h-full flex flex-col backdrop-blur-glass-medium">
      <div className="flex justify-between items-center p-4 border-b border-glass-border-tertiary">
        <h3 className="font-semibold text-foreground flex items-center gap-2">
          <MessageSquareIcon className="h-5 w-5 text-primary" />
          Chat Sessions
        </h3>
        <LiquidButton 
          variant="glass" 
          size="icon" 
          onClick={() => createSession('New Chat')}
          className="hover:scale-105 transition-transform duration-200"
        >
          <PlusIcon className="h-5 w-5" />
        </LiquidButton>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sessionsLoading && (
          <div className="flex justify-center py-4">
            <LoadingSpinner />
          </div>
        )}
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => switchSession(session.id)}
            className={cn(
              'w-full text-left flex items-center gap-3 p-3 rounded-xl text-sm transition-all duration-200 hover:scale-[1.02]',
              currentSession?.id === session.id
                ? 'bg-primary/20 backdrop-blur-md text-foreground font-semibold border border-primary/30 shadow-lg'
                : 'hover:bg-glass-bg-tertiary text-muted-foreground hover:backdrop-blur-md hover:border hover:border-glass-border-secondary'
            )}
          >
            <div className={cn(
              'p-2 rounded-lg transition-colors',
              currentSession?.id === session.id
                ? 'bg-primary/30'
                : 'bg-glass-bg-secondary'
            )}>
              <MessageSquareIcon className="h-4 w-4 flex-shrink-0" />
            </div>
            <span className="truncate flex-1">{session.title}</span>
          </button>
        ))}
        {sessions.length === 0 && !sessionsLoading && (
          <div className="text-center py-8 text-muted-foreground">
            <MessageSquareIcon className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p className="text-sm">No chat sessions yet</p>
            <p className="text-xs mt-1">Create a new chat to get started</p>
          </div>
        )}
      </div>
    </GlassPanel>
  );
}

function Message({ role, content }: { role: 'user' | 'assistant', content: string }) {
  const Icon = role === 'user' ? User : Bot;
  const isUser = role === 'user';
  
  return (
    <div className={cn(
      "flex items-start gap-4 mb-6 animate-fade-in",
      isUser ? 'justify-end' : ''
    )}>
      {!isUser && (
        <div className="flex-shrink-0 p-2 rounded-full bg-gradient-to-br from-primary/20 to-primary/10 backdrop-blur-md border border-primary/20">
          <Icon className="h-5 w-5 text-primary" />
        </div>
      )}
      
      <div className={cn(
        "max-w-2xl p-4 rounded-2xl shadow-lg backdrop-blur-md transition-all duration-200 hover:shadow-xl",
        isUser 
          ? 'bg-gradient-to-br from-primary to-primary/90 text-primary-foreground border border-primary/20' 
          : 'bg-glass-bg-primary border border-glass-border-primary'
      )}>
        <div className={cn(
          "prose max-w-none whitespace-pre-wrap leading-relaxed",
          isUser ? "prose-invert text-primary-foreground" : "text-foreground"
        )}>
          {content}
        </div>
      </div>
      
      {isUser && (
        <div className="flex-shrink-0 p-2 rounded-full bg-gradient-to-br from-primary/20 to-primary/10 backdrop-blur-md border border-primary/20">
          <Icon className="h-5 w-5 text-primary" />
        </div>
      )}
    </div>
  )
}

function ChatInput() {
  const { sendMessage, isTyping } = useChatStore();
  const [input, setInput] = React.useState('');
  const [showSuggestions, setShowSuggestions] = React.useState(false);
  
  const suggestions = [
    { icon: Sparkles, text: "Summarize my knowledge base" },
    { icon: Search, text: "Find information about..." },
    { icon: FileText, text: "Create a document from my data" }
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage(input.trim());
    setInput('');
    setShowSuggestions(false);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
    setShowSuggestions(false);
  };

  return (
    <div className="p-6 bg-glass-bg-secondary/50 backdrop-blur-md border-t border-glass-border-tertiary">
      {/* Suggestions */}
      {!input && !isTyping && (
        <div className="mb-4">
          <div className="flex gap-2 justify-center flex-wrap">
            {suggestions.map((suggestion, index) => (
              <button
                key={index}
                onClick={() => handleSuggestionClick(suggestion.text)}
                className="flex items-center gap-2 px-4 py-2 rounded-full bg-glass-bg-tertiary hover:bg-glass-bg-secondary 
                          border border-glass-border-tertiary hover:border-glass-border-secondary 
                          transition-all duration-200 hover:scale-105 text-sm text-muted-foreground hover:text-foreground"
              >
                <suggestion.icon className="h-4 w-4" />
                <span>{suggestion.text}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      
      <form onSubmit={handleSubmit}>
        <div className="relative">
          <GlassInput
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Message the AI assistant... (reference your knowledge base)"
            className="pr-16 h-14 text-base rounded-full border-glass-border-primary hover:border-primary/50 focus:border-primary/70 shadow-lg"
            disabled={isTyping}
            onFocus={() => setShowSuggestions(true)}
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
            {input.trim() && (
              <span className="text-xs text-muted-foreground bg-glass-bg-tertiary px-2 py-1 rounded-full">
                ⏎ Send
              </span>
            )}
            <LiquidButton 
              type="submit" 
              size="icon" 
              variant="glass"
              className="h-10 w-10 rounded-full shadow-lg disabled:opacity-50 transition-all duration-200 hover:scale-105" 
              disabled={isTyping || !input.trim()}
            >
              <SendIcon className="h-5 w-5" />
            </LiquidButton>
          </div>
        </div>
      </form>
      
      {/* Typing indicator */}
      {isTyping && (
        <div className="flex items-center justify-center gap-2 mt-4 text-muted-foreground">
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce"></div>
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
          </div>
          <span className="text-sm">AI is thinking...</span>
        </div>
      )}
    </div>
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
      <GlassPanel variant="primary" className="h-full flex items-center justify-center backdrop-blur-glass-strong">
        <div className="text-center max-w-md">
          <div className="p-4 rounded-full bg-glass-bg-secondary mx-auto w-fit mb-4">
            <MessageSquareIcon className="h-12 w-12 text-primary" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">Start Your Conversation</h3>
          <p className="text-muted-foreground mb-6">
            Select an existing chat session or create a new one to begin chatting with your AI assistant.
          </p>
          <LiquidButton variant="glass" onClick={() => {}}>
            <PlusIcon className="h-4 w-4 mr-2" />
            Create New Chat
          </LiquidButton>
        </div>
      </GlassPanel>
    )
  }

  const hasMessages = messages && messages.length > 0;

  return (
    <GlassPanel variant="primary" className="h-full flex flex-col backdrop-blur-glass-strong">
      {/* Chat Header */}
      <div className="flex items-center justify-between p-4 border-b border-glass-border-tertiary bg-glass-bg-secondary/30">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-full bg-primary/20">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold text-foreground">AI Assistant</h3>
            <p className="text-xs text-muted-foreground">
              Connected to your knowledge base
            </p>
          </div>
        </div>
        <div className="text-xs text-muted-foreground bg-glass-bg-tertiary px-3 py-1 rounded-full">
          {messages?.length || 0} messages
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        {messagesLoading && (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        )}
        
        {!hasMessages && !messagesLoading && !isTyping && (
          <div className="h-full flex items-center justify-center p-8">
            <div className="text-center max-w-lg">
              <div className="p-4 rounded-full bg-gradient-to-br from-primary/20 to-primary/10 mx-auto w-fit mb-6">
                <Sparkles className="h-16 w-16 text-primary" />
              </div>
              <h3 className="text-xl font-semibold text-foreground mb-3">
                Ready to Help!
              </h3>
              <p className="text-muted-foreground mb-6 leading-relaxed">
                I'm your AI assistant with access to your knowledge base. Ask me anything – 
                I can help summarize information, find specific details, or create documents from your data.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div className="p-3 rounded-xl bg-glass-bg-secondary border border-glass-border-secondary">
                  <Search className="h-5 w-5 text-primary mb-2" />
                  <div className="font-medium text-foreground">Search Knowledge</div>
                  <div className="text-muted-foreground">Find specific information in your data</div>
                </div>
                <div className="p-3 rounded-xl bg-glass-bg-secondary border border-glass-border-secondary">
                  <FileText className="h-5 w-5 text-primary mb-2" />
                  <div className="font-medium text-foreground">Generate Summaries</div>
                  <div className="text-muted-foreground">Create concise overviews of topics</div>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {hasMessages && (
          <div className="p-6 space-y-2">
            {messages.map((msg) => (
              <Message key={msg.id} role={msg.role} content={msg.content} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-4 border-t border-glass-border-tertiary">
          <Alert variant="destructive" className="bg-red-500/10 border-red-500/20">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}

      {/* Chat Input */}
      <ChatInput />
    </GlassPanel>
  );
}

export function Chat() {
  return (
    <div className="flex gap-6 h-full p-4">
      <div className="w-[320px] hidden lg:block">
        <SessionPanel />
      </div>
      <div className="flex-1 h-full min-w-0">
        <ChatPanel />
      </div>
    </div>
  );
}
