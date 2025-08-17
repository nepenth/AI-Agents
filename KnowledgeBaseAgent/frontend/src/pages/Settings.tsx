import React, { useEffect, useState } from 'react';
import { useSettingsStore } from '@/stores/settingsStore';
import { useThemeStore } from '@/stores/themeStore';
import type { ModelPhase, PhaseModelSelector } from '@/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';

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
                <Select
                  className="flex-1"
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
                  <option value="">Select Backend</option>
                  {backends.map((b) => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </Select>
                <Select
                  className="flex-1"
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
                  <option value="">Select Model</option>
                  {models.map((m: string) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </Select>
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-6 flex justify-end">
        <Button onClick={onSave} disabled={isLoading}>
          {isLoading ? 'Saving...' : 'Save Configuration'}
        </Button>
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
        <div className="flex items-center gap-3">
          <Checkbox
            id="reduce-motion"
            checked={reduceMotion}
            onCheckedChange={toggleReduceMotion}
          />
          <label htmlFor="reduce-motion" className="text-sm text-foreground cursor-pointer">
            Reduce motion
          </label>
        </div>
        <div className="flex items-center gap-3">
          <Checkbox
            id="increase-contrast"
            checked={increaseContrast}
            onCheckedChange={toggleIncreaseContrast}
          />
          <label htmlFor="increase-contrast" className="text-sm text-foreground cursor-pointer">
            Increase contrast
          </label>
        </div>
        <div className="flex items-center gap-3">
          <Checkbox
            id="reduce-transparency"
            checked={reduceTransparency}
            onCheckedChange={toggleReduceTransparency}
          />
          <label htmlFor="reduce-transparency" className="text-sm text-foreground cursor-pointer">
            Reduce transparency
          </label>
        </div>
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