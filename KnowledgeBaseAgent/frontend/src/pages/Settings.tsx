import React, { useEffect, useState } from 'react';
import { useSettingsStore } from '@/stores/settingsStore';
import type { ModelPhase, PhaseModelSelector } from '@/types';

const PHASES: ModelPhase[] = ['vision', 'kb_generation', 'synthesis', 'chat', 'embeddings'];

export function Settings() {
  const { loadAvailable, available, loadConfig, modelsByPhase, saveConfig, isLoading, error } = useSettingsStore();
  const [draft, setDraft] = useState<Record<ModelPhase, PhaseModelSelector | null>>(modelsByPhase);

  useEffect(() => {
    loadAvailable();
    loadConfig();
  }, []);

  useEffect(() => {
    setDraft(modelsByPhase);
  }, [modelsByPhase]);

  const backends = Object.keys(available);

  const onSave = async () => {
    await saveConfig(draft);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-gray-900">Settings</h2>
        <p className="text-sm text-gray-600">Configure AI models per phase</p>
      </div>

      {error && <div className="text-red-600 text-sm">{error}</div>}

      <div className="card p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {PHASES.map((phase) => {
            const selector = draft[phase];
            const selectedBackend = selector?.backend || backends[0];
            const backendInfo = selectedBackend ? available[selectedBackend] : undefined;
            const models = backendInfo?.models || [];

            return (
              <div key={phase} className="space-y-3">
                <div className="text-sm font-medium text-gray-900 capitalize">{phase.replace('_', ' ')}</div>
                <div className="flex gap-3">
                  <select
                    className="input"
                    value={selectedBackend || ''}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                      const backend = e.target.value as PhaseModelSelector['backend'];
                      setDraft({
                        ...draft,
                        [phase]: {
                          backend,
                          model: available[backend]?.models?.[0] || '',
                          params: selector?.params || {},
                        },
                      });
                    }}
                  >
                    {backends.map((b) => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                  <select
                    className="input"
                    value={selector?.model || ''}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                      const model = e.target.value;
                      if (!selectedBackend) return;
                      setDraft({
                        ...draft,
                        [phase]: {
                          backend: selectedBackend,
                          model,
                          params: selector?.params || {},
                        },
                      });
                    }}
                  >
                    {models.map((m: string) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-6 flex justify-end">
          <button className="btn-primary px-4 py-2" onClick={onSave} disabled={isLoading}>
            {isLoading ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>

      <div className="card p-6">
        <div className="space-y-3">
          <div className="text-sm font-medium text-gray-900">Appearance</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" className="rounded" /> Reduce motion
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" className="rounded" /> Increase contrast
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" className="rounded" /> Reduce transparency
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}