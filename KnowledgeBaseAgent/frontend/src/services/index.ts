// API Services
export { apiService, APIService, APIError } from './api';
export { websocketService, WebSocketService } from './websocket';

// Domain Services
export { agentService, AgentService } from './agentService';
export { knowledgeService, KnowledgeService } from './knowledgeService';
export { chatService, ChatService } from './chatService';

// Types
export type { AgentConfig, StartAgentRequest, TaskHistoryParams } from './agentService';
export type { 
  CreateKnowledgeItemRequest, 
  UpdateKnowledgeItemRequest, 
  SearchRequest,
  Category,
  SynthesisDocument 
} from './knowledgeService';
export type { 
  CreateChatSessionRequest, 
  SendMessageRequest, 
  ChatResponse 
} from './chatService';
export type { WebSocketEventHandler } from './websocket';