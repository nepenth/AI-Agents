import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { ChatSession, ChatMessage } from '@/types';
import { chatService, ChatResponse } from '@/services/chatService';

interface ChatState {
  // Sessions
  sessions: ChatSession[];
  sessionsLoading: boolean;
  currentSession: ChatSession | null;
  
  // Messages
  messages: ChatMessage[];
  messagesLoading: boolean;
  
  // Chat state
  isTyping: boolean;
  isConnected: boolean;
  streamingMessage: string;
  
  // Available models
  availableModels: Array<{
    id: string;
    name: string;
    provider: string;
    capabilities: string[];
    context_length: number;
    is_available: boolean;
  }>;
  selectedModel: string;
  
  // Settings
  chatSettings: {
    temperature: number;
    max_tokens: number;
    use_knowledge_base: boolean;
  };
  
  // Loading and error states
  loading: boolean;
  error: string | null;
  
  // Actions
  loadSessions: () => Promise<void>;
  createSession: (title?: string) => Promise<ChatSession>;
  switchSession: (sessionId: string) => Promise<void>;
  updateSession: (sessionId: string, updates: any) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  
  // Messages
  loadMessages: (sessionId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  deleteMessage: (messageId: string) => Promise<void>;
  regenerateResponse: (messageId: string) => Promise<void>;
  
  // Real-time
  startStreaming: () => void;
  updateStreamingMessage: (chunk: string) => void;
  finishStreaming: () => void;
  
  // Models and settings
  loadAvailableModels: () => Promise<void>;
  setSelectedModel: (modelId: string) => void;
  updateChatSettings: (settings: Partial<ChatState['chatSettings']>) => void;
  
  // Utility
  clearError: () => void;
  reset: () => void;
}

export const useChatStore = create<ChatState>()(
  devtools(
    (set, get) => ({
      // Initial state
      sessions: [],
      sessionsLoading: false,
      currentSession: null,
      messages: [],
      messagesLoading: false,
      isTyping: false,
      isConnected: false,
      streamingMessage: '',
      availableModels: [],
      selectedModel: '',
      chatSettings: {
        temperature: 0.7,
        max_tokens: 2000,
        use_knowledge_base: true,
      },
      loading: false,
      error: null,

      // Session Actions
      loadSessions: async () => {
        set({ sessionsLoading: true, error: null });
        try {
          const response = await chatService.getChatSessions();
          set({
            sessions: response.items,
            sessionsLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to load sessions',
            sessionsLoading: false,
          });
        }
      },

      createSession: async (title?: string) => {
        set({ loading: true, error: null });
        try {
          const session = await chatService.createChatSession({ title });
          const { sessions } = get();
          set({
            sessions: [session, ...sessions],
            currentSession: session,
            messages: [],
            loading: false,
          });
          return session;
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to create session',
            loading: false,
          });
          throw error;
        }
      },

      switchSession: async (sessionId: string) => {
        set({ loading: true, error: null });
        try {
          const session = await chatService.getChatSession(sessionId);
          set({
            currentSession: session,
            loading: false,
          });
          await get().loadMessages(sessionId);
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to switch session',
            loading: false,
          });
        }
      },

      updateSession: async (sessionId: string, updates: any) => {
        try {
          const updatedSession = await chatService.updateChatSession(sessionId, updates);
          const { sessions, currentSession } = get();
          set({
            sessions: sessions.map(s => s.id === sessionId ? updatedSession : s),
            currentSession: currentSession?.id === sessionId ? updatedSession : currentSession,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to update session',
          });
          throw error;
        }
      },

      deleteSession: async (sessionId: string) => {
        try {
          await chatService.deleteChatSession(sessionId);
          const { sessions, currentSession } = get();
          set({
            sessions: sessions.filter(s => s.id !== sessionId),
            currentSession: currentSession?.id === sessionId ? null : currentSession,
            messages: currentSession?.id === sessionId ? [] : get().messages,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to delete session',
          });
          throw error;
        }
      },

      // Message Actions
      loadMessages: async (sessionId: string) => {
        set({ messagesLoading: true, error: null });
        try {
          const response = await chatService.getChatMessages(sessionId);
          set({
            messages: response.items,
            messagesLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to load messages',
            messagesLoading: false,
          });
        }
      },

      sendMessage: async (content: string) => {
        const { currentSession, chatSettings, selectedModel } = get();
        if (!currentSession) return;

        // Add user message immediately
        const userMessage: ChatMessage = {
          id: `temp-${Date.now()}`,
          session_id: currentSession.id,
          role: 'user',
          content,
          sources: [],
          created_at: new Date().toISOString(),
        };

        set({
          messages: [...get().messages, userMessage],
          isTyping: true,
          error: null,
        });

        try {
          const response = await chatService.sendMessage(currentSession.id, {
            content,
            model: selectedModel,
            ...chatSettings,
          });

          // Replace temp message and add AI response
          const aiMessage: ChatMessage = {
            id: response.id,
            session_id: currentSession.id,
            role: 'assistant',
            content: response.content,
            model_used: response.model_used,
            sources: response.sources.map(s => s.id),
            context_stats: response.context_stats,
            created_at: response.created_at,
          };

          set({
            messages: [
              ...get().messages.filter(m => m.id !== userMessage.id),
              { ...userMessage, id: `user-${Date.now()}` },
              aiMessage,
            ],
            isTyping: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to send message',
            isTyping: false,
          });
          throw error;
        }
      },

      deleteMessage: async (messageId: string) => {
        const { currentSession } = get();
        if (!currentSession) return;

        try {
          await chatService.deleteMessage(currentSession.id, messageId);
          set({
            messages: get().messages.filter(m => m.id !== messageId),
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to delete message',
          });
          throw error;
        }
      },

      regenerateResponse: async (messageId: string) => {
        const { currentSession, selectedModel, chatSettings } = get();
        if (!currentSession) return;

        set({ isTyping: true, error: null });
        try {
          const response = await chatService.regenerateResponse(
            currentSession.id,
            messageId,
            { model: selectedModel, ...chatSettings }
          );

          const newMessage: ChatMessage = {
            id: response.id,
            session_id: currentSession.id,
            role: 'assistant',
            content: response.content,
            model_used: response.model_used,
            sources: response.sources.map(s => s.id),
            context_stats: response.context_stats,
            created_at: response.created_at,
          };

          set({
            messages: get().messages.map(m => m.id === messageId ? newMessage : m),
            isTyping: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to regenerate response',
            isTyping: false,
          });
          throw error;
        }
      },

      // Real-time Actions
      startStreaming: () => set({ isTyping: true, streamingMessage: '' }),

      updateStreamingMessage: (chunk: string) => {
        set({ streamingMessage: get().streamingMessage + chunk });
      },

      finishStreaming: () => {
        const { streamingMessage, messages, currentSession } = get();
        if (!currentSession || !streamingMessage) return;

        const aiMessage: ChatMessage = {
          id: `stream-${Date.now()}`,
          session_id: currentSession.id,
          role: 'assistant',
          content: streamingMessage,
          sources: [],
          created_at: new Date().toISOString(),
        };

        set({
          messages: [...messages, aiMessage],
          isTyping: false,
          streamingMessage: '',
        });
      },

      // Model and Settings Actions
      loadAvailableModels: async () => {
        try {
          const models = await chatService.getAvailableModels();
          set({
            availableModels: models,
            selectedModel: get().selectedModel || models.find(m => m.is_available)?.id || '',
          });
        } catch (error) {
          console.error('Failed to load available models:', error);
        }
      },

      setSelectedModel: (modelId: string) => set({ selectedModel: modelId }),

      updateChatSettings: (settings) => {
        const { chatSettings } = get();
        set({ chatSettings: { ...chatSettings, ...settings } });
      },

      // Utility
      clearError: () => set({ error: null }),

      reset: () => set({
        sessions: [],
        currentSession: null,
        messages: [],
        isTyping: false,
        streamingMessage: '',
        error: null,
        loading: false,
      }),
    }),
    {
      name: 'chat-store',
    }
  )
);