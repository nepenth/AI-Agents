import React, { useEffect, useState } from 'react';
import { useSettingsStore } from '@/stores/settingsStore';
import { useThemeStore } from '@/stores/themeStore';
import type { ModelPhase, PhaseModelSelector } from '@/types';
import { GlassCard } from '@/components/ui/GlassCard';

const PHASES: ModelPhase[] = ['vision', 'kb_generation', 'synthesis', 'chat', 'embeddings'];

function ModelSettings() {
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
    <GlassCard>
      <h3 className="text-lg font-semibold text-foreground mb-4">AI Model Configuration</h3>
      {error && <div className="text-destructive text-sm mb-4">{error}</div>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {PHASES.map((phase) => {
          const selector = draft[phase];
          const selectedBackend = selector?.backend || backends[0];
          const backendInfo = selectedBackend ? available[selectedBackend] : undefined;
          const models = backendInfo?.models || [];

          return (
            <div key={phase} className="space-y-2">
              <div className="text-sm font-medium text-foreground capitalize">{phase.replace(/_/g, ' ')}</div>
              <div className="flex gap-2">
                <select
                  className="input flex-1"
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
                  className="input flex-1"
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
    </GlassCard>
  );
}

function AppearanceSettings() {
  const {
    reduceMotion, toggleReduceMotion,
    increaseContrast, toggleIncreaseContrast,
    reduceTransparency, toggleReduceTransparency
  } = useThemeStore();

  return (
    <GlassCard>
      <h3 className="text-lg font-semibold text-foreground mb-4">Appearance</h3>
      <div className="space-y-3">
        <label className="flex items-center gap-3 text-sm text-foreground">
          <input type="checkbox" className="rounded" checked={reduceMotion} onChange={toggleReduceMotion} />
          Reduce motion
        </label>
        <label className="flex items-center gap-3 text-sm text-foreground">
          <input type="checkbox" className="rounded" checked={increaseContrast} onChange={toggleIncreaseContrast} />
          Increase contrast
        </label>
        <label className="flex items-center gap-3 text-sm text-foreground">
          <input type="checkbox" className="rounded" checked={reduceTransparency} onChange={toggleReduceTransparency} />
          Reduce transparency
        </label>
      </div>
    </GlassCard>
  );
}


export function Settings() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Settings</h2>
        <p className="text-muted-foreground">
          Manage your agent's configuration and application appearance.
        </p>
      </div>

      <ModelSettings />
      <AppearanceSettings />
    </div>
  );
}