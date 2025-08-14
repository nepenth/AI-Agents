import { create } from 'zustand';
import { apiService } from '@/services/api';
import type { ModelPhase, PhaseModelSelector, ModelsAvailableResponse, ModelsConfigResponse } from '@/types';

interface SettingsState {
  modelsByPhase: Record<ModelPhase, PhaseModelSelector | null>;
  available: ModelsAvailableResponse['backends'];
  isLoading: boolean;
  error?: string;
  loadAvailable: () => Promise<void>;
  loadConfig: () => Promise<void>;
  saveConfig: (config: Record<ModelPhase, PhaseModelSelector | null>) => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  modelsByPhase: {
    vision: null,
    kb_generation: null,
    synthesis: null,
    chat: null,
    embeddings: null,
  },
  available: {},
  isLoading: false,
  async loadAvailable() {
    set({ isLoading: true, error: undefined });
    try {
      const res = await apiService.get<ModelsAvailableResponse>('/system/models/available');
      set({ available: res.backends, isLoading: false });
    } catch (e: any) {
      set({ error: e?.message || 'Failed to load models', isLoading: false });
    }
  },
  async loadConfig() {
    set({ isLoading: true, error: undefined });
    try {
      const res = await apiService.get<ModelsConfigResponse>('/system/models/config');
      set({ modelsByPhase: res.per_phase, isLoading: false });
    } catch (e: any) {
      set({ error: e?.message || 'Failed to load model config', isLoading: false });
    }
  },
  async saveConfig(config) {
    set({ isLoading: true, error: undefined });
    try {
      const res = await apiService.put<ModelsConfigResponse>('/system/models/config', { per_phase: config });
      set({ modelsByPhase: res.per_phase, isLoading: false });
    } catch (e: any) {
      set({ error: e?.message || 'Failed to save model config', isLoading: false });
    }
  },
}));


