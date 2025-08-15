import React from 'react'
import { Settings, Eye, Type, Contrast, Zap, Keyboard, Volume2 } from 'lucide-react'
import { GlassCard } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Switch } from '@/components/ui/Switch'
import { useAccessibility } from '@/contexts/AccessibilityContext'
import { cn } from '@/utils/cn'

interface AccessibilitySettingsProps {
  className?: string
}

export function AccessibilitySettings({ className }: AccessibilitySettingsProps) {
  const { settings, updateSetting, resetSettings, announceToScreenReader } = useAccessibility()

  const settingsConfig = [
    {
      key: 'reduceMotion' as const,
      label: 'Reduce Motion',
      description: 'Minimize animations and transitions',
      icon: Zap,
      category: 'Visual'
    },
    {
      key: 'increaseContrast' as const,
      label: 'Increase Contrast',
      description: 'Use higher contrast colors for better visibility',
      icon: Contrast,
      category: 'Visual'
    },
    {
      key: 'reduceTransparency' as const,
      label: 'Reduce Transparency',
      description: 'Use solid backgrounds instead of transparent ones',
      icon: Eye,
      category: 'Visual'
    },
    {
      key: 'largeText' as const,
      label: 'Large Text',
      description: 'Increase text size throughout the interface',
      icon: Type,
      category: 'Visual'
    },
    {
      key: 'focusVisible' as const,
      label: 'Enhanced Focus Indicators',
      description: 'Show clear focus indicators for keyboard navigation',
      icon: Keyboard,
      category: 'Navigation'
    },
    {
      key: 'screenReaderOptimized' as const,
      label: 'Screen Reader Optimization',
      description: 'Optimize interface for screen reader users',
      icon: Volume2,
      category: 'Assistive Technology'
    },
    {
      key: 'keyboardNavigation' as const,
      label: 'Enhanced Keyboard Navigation',
      description: 'Improve keyboard navigation with additional shortcuts',
      icon: Keyboard,
      category: 'Navigation'
    }
  ]

  const categories = Array.from(new Set(settingsConfig.map(s => s.category)))

  const handleSettingChange = (key: keyof typeof settings, value: boolean) => {
    updateSetting(key, value)
    announceToScreenReader(
      `${settingsConfig.find(s => s.key === key)?.label} ${value ? 'enabled' : 'disabled'}`,
      'polite'
    )
  }

  const handleReset = () => {
    resetSettings()
    announceToScreenReader('Accessibility settings reset to defaults', 'polite')
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings className="h-6 w-6" />
          <h2 className="text-2xl font-bold">Accessibility Settings</h2>
        </div>
        <Button variant="outline" onClick={handleReset}>
          Reset to Defaults
        </Button>
      </div>

      <p className="text-muted-foreground">
        Customize the interface to meet your accessibility needs. These settings are saved locally and will persist across sessions.
      </p>

      {/* Settings by Category */}
      {categories.map(category => (
        <GlassCard key={category} className="p-6">
          <h3 className="text-lg font-semibold mb-4">{category}</h3>
          
          <div className="space-y-4">
            {settingsConfig
              .filter(setting => setting.category === category)
              .map(setting => {
                const Icon = setting.icon
                const isEnabled = settings[setting.key]
                
                return (
                  <div
                    key={setting.key}
                    className="flex items-start justify-between p-4 rounded-lg border border-border hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex items-start gap-3 flex-1">
                      <div className={cn(
                        'p-2 rounded-md',
                        isEnabled ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                      )}>
                        <Icon className="h-4 w-4" />
                      </div>
                      
                      <div className="flex-1">
                        <label 
                          htmlFor={`setting-${setting.key}`}
                          className="text-sm font-medium text-foreground cursor-pointer"
                        >
                          {setting.label}
                        </label>
                        <p className="text-xs text-muted-foreground mt-1">
                          {setting.description}
                        </p>
                      </div>
                    </div>
                    
                    <Switch
                      id={`setting-${setting.key}`}
                      checked={isEnabled}
                      onCheckedChange={(checked) => handleSettingChange(setting.key, checked)}
                      aria-describedby={`setting-${setting.key}-description`}
                    />
                    
                    {/* Hidden description for screen readers */}
                    <span 
                      id={`setting-${setting.key}-description`}
                      className="sr-only"
                    >
                      {setting.description}
                    </span>
                  </div>
                )
              })}
          </div>
        </GlassCard>
      ))}

      {/* Quick Actions */}
      <GlassCard className="p-6">
        <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <Button
            variant="outline"
            onClick={() => {
              updateSetting('reduceMotion', true)
              updateSetting('increaseContrast', true)
              announceToScreenReader('High contrast mode enabled', 'polite')
            }}
            className="justify-start"
          >
            <Contrast className="h-4 w-4 mr-2" />
            High Contrast Mode
          </Button>
          
          <Button
            variant="outline"
            onClick={() => {
              updateSetting('largeText', true)
              updateSetting('focusVisible', true)
              announceToScreenReader('Large text mode enabled', 'polite')
            }}
            className="justify-start"
          >
            <Type className="h-4 w-4 mr-2" />
            Large Text Mode
          </Button>
          
          <Button
            variant="outline"
            onClick={() => {
              updateSetting('screenReaderOptimized', true)
              updateSetting('keyboardNavigation', true)
              updateSetting('focusVisible', true)
              announceToScreenReader('Screen reader optimization enabled', 'polite')
            }}
            className="justify-start"
          >
            <Volume2 className="h-4 w-4 mr-2" />
            Screen Reader Mode
          </Button>
        </div>
      </GlassCard>

      {/* System Preferences Detection */}
      <GlassCard className="p-6">
        <h3 className="text-lg font-semibold mb-4">System Preferences</h3>
        <p className="text-sm text-muted-foreground mb-4">
          We automatically detect and respect your system accessibility preferences.
        </p>
        
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span>Prefers Reduced Motion:</span>
            <span className={cn(
              'font-medium',
              window.matchMedia('(prefers-reduced-motion: reduce)').matches 
                ? 'text-green-600' 
                : 'text-muted-foreground'
            )}>
              {window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'Yes' : 'No'}
            </span>
          </div>
          
          <div className="flex justify-between">
            <span>Prefers High Contrast:</span>
            <span className={cn(
              'font-medium',
              window.matchMedia('(prefers-contrast: high)').matches 
                ? 'text-green-600' 
                : 'text-muted-foreground'
            )}>
              {window.matchMedia('(prefers-contrast: high)').matches ? 'Yes' : 'No'}
            </span>
          </div>
          
          <div className="flex justify-between">
            <span>Prefers Reduced Transparency:</span>
            <span className={cn(
              'font-medium',
              window.matchMedia('(prefers-reduced-transparency: reduce)').matches 
                ? 'text-green-600' 
                : 'text-muted-foreground'
            )}>
              {window.matchMedia('(prefers-reduced-transparency: reduce)').matches ? 'Yes' : 'No'}
            </span>
          </div>
        </div>
      </GlassCard>
    </div>
  )
}