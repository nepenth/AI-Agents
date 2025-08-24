import React, { useEffect, useState } from 'react';
import { useSettingsStore } from '@/stores/settingsStore';
import { useThemeStore } from '@/stores/themeStore';
import type { ModelPhase, PhaseModelSelector } from '@/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { LiquidButton } from '@/components/ui/LiquidButton';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PageLayout, PageHeader, PageSection, PageContent } from '@/components/layout/PageLayout';
import { Alert, AlertDescription } from '@/components/ui/Alert';
import { Switch } from '@/components/ui/Switch';
import { BrainIcon, PaletteIcon, AlertTriangleIcon } from 'lucide-react';
import { cn } from '@/utils/cn';

const PHASES: ModelPhase[] = ['vision', 'kb_generation', 'synthesis', 'chat', 'embeddings'];

function ModelSettings() {
  const { loadAvailable, available, loadConfig, modelsByPhase, saveConfig, isLoading, error } = useSettingsStore();
  const [draft, setDraft] = useState<Record<ModelPhase, PhaseModelSelector | null>>(modelsByPhase);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    loadAvailable();
    loadConfig();
  }, []);

  useEffect(() => {
    setDraft(modelsByPhase);
    setHasChanges(false);
  }, [modelsByPhase]);

  useEffect(() => {
    const changed = JSON.stringify(draft) !== JSON.stringify(modelsByPhase);
    setHasChanges(changed);
  }, [draft, modelsByPhase]);

  const backends = Object.keys(available);

  const onSave = async () => {
    await saveConfig(draft);
    setHasChanges(false);
  };

  const onReset = () => {
    setDraft(modelsByPhase);
    setHasChanges(false);
  };

  return (
    <GlassCard variant="primary" className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-primary/20 rounded-lg">
          <BrainIcon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-foreground">AI Model Configuration</h3>
          <p className="text-sm text-muted-foreground">Configure AI models for different processing phases</p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangleIcon className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {PHASES.map((phase) => {
          const selector = draft[phase];
          const selectedBackend = selector?.backend || backends[0];
          const backendInfo = selectedBackend ? available[selectedBackend] : undefined;
          const models = backendInfo?.models || [];

          return (
            <div key={phase} className="space-y-3">
              <div className="text-sm font-medium text-foreground capitalize">
                {phase.replace(/_/g, ' ')}
              </div>
              <div className="space-y-2">
                <select
                  className={cn(
                    "w-full px-3 py-2 bg-glass-secondary border border-glass-border-secondary",
                    "rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/50",
                    "focus:border-primary/50 transition-all"
                  )}
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
                  className={cn(
                    "w-full px-3 py-2 bg-glass-secondary border border-glass-border-secondary",
                    "rounded-lg text-foreground text-sm focus:ring-2 focus:ring-primary/50",
                    "focus:border-primary/50 transition-all"
                  )}
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
      
      <div className="flex items-center justify-between pt-4 border-t border-white/10">
        <div className="text-sm text-muted-foreground">
          {hasChanges ? 'You have unsaved changes' : 'All changes saved'}
        </div>
        <div className="flex items-center gap-3">
          {hasChanges && (
            <LiquidButton variant="outline" size="sm" onClick={onReset}>
              Reset
            </LiquidButton>
          )}
          <LiquidButton 
            variant="primary" 
            size="sm" 
            onClick={onSave} 
            disabled={isLoading || !hasChanges}
            className="min-w-[100px]"
          >
            {isLoading ? (
              <><LoadingSpinner size="sm" className="mr-2" />Saving...</>
            ) : (
              'Save Changes'
            )}
          </LiquidButton>
        </div>
      </div>
    </GlassCard>
  );
}

function AppearanceSettings() {
  const {
    reduceMotion, setReduceMotion,
    increaseContrast, setIncreaseContrast,
    reduceTransparency, setReduceTransparency
  } = useThemeStore();

  const settings = [
    {
      id: 'reduce-motion',
      label: 'Reduce motion',
      description: 'Minimize animations and transitions for better accessibility',
      checked: reduceMotion,
      onChange: () => setReduceMotion(!reduceMotion)
    },
    {
      id: 'increase-contrast',
      label: 'Increase contrast',
      description: 'Enhance text and element contrast for better readability',
      checked: increaseContrast,
      onChange: () => setIncreaseContrast(!increaseContrast)
    },
    {
      id: 'reduce-transparency',
      label: 'Reduce transparency',
      description: 'Reduce glass effects and transparency for better performance',
      checked: reduceTransparency,
      onChange: () => setReduceTransparency(!reduceTransparency)
    }
  ];

  return (
    <GlassCard variant="secondary" className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-secondary/20 rounded-lg">
          <PaletteIcon className="h-5 w-5 text-secondary" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-foreground">Appearance & Accessibility</h3>
          <p className="text-sm text-muted-foreground">Customize the visual appearance and accessibility features</p>
        </div>
      </div>

      <div className="space-y-4">
        {settings.map((setting) => (
          <div key={setting.id} className="flex items-center justify-between py-3 border-b border-white/5 last:border-b-0">
            <div className="flex-1">
              <div className="text-sm font-medium text-foreground mb-1">
                {setting.label}
              </div>
              <div className="text-xs text-muted-foreground">
                {setting.description}
              </div>
            </div>
            <Switch
              checked={setting.checked}
              onCheckedChange={setting.onChange}
              aria-labelledby={`${setting.id}-label`}
            />
          </div>
        ))}
      </div>
    </GlassCard>
  );
}


export function Settings() {
  return (
    <PageLayout maxWidth="xl" spacing="lg">
      <PageHeader
        title="Settings"
        description="Manage your agent's configuration and application appearance."
      />
      
      <PageContent layout="single" gap="lg">
        <PageSection spacing="lg">
          <ModelSettings />
        </PageSection>
        
        <PageSection spacing="lg">
          <AppearanceSettings />
        </PageSection>
      </PageContent>
    </PageLayout>
  );
}