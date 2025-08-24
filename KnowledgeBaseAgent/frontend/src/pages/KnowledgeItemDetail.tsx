import * as React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useKnowledgeStore } from '@/stores';
import { GlassCard } from '@/components/ui/GlassCard';
import { LiquidButton } from '@/components/ui/LiquidButton';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { PageLayout, PageHeader, PageSection, PageContent } from '@/components/layout/PageLayout';
import { ExternalLinkIcon, ArrowLeftIcon, CopyIcon, CalendarIcon, TagIcon } from 'lucide-react';
import { cn } from '@/utils/cn';

function ItemMetadata({ item }: { item: any }) {
  const metadata = [
    {
      label: 'Created',
      value: new Date(item.created_at).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      }),
      icon: CalendarIcon
    },
    item.content_item_id && {
      label: 'Source ID',
      value: item.content_item_id,
      icon: TagIcon
    }
  ].filter(Boolean);

  return (
    <div className="flex flex-wrap gap-4 text-sm">
      {metadata.map((meta, index) => {
        const Icon = meta!.icon;
        return (
          <div key={index} className="flex items-center gap-2 text-muted-foreground">
            <Icon className="h-4 w-4" />
            <span className="font-medium">{meta!.label}:</span>
            <span>{meta!.value}</span>
          </div>
        );
      })}
    </div>
  );
}

function ContentSection({ title, children, icon: Icon, onCopy }: { 
  title: string; 
  children: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  onCopy?: () => void;
}) {
  return (
    <div className="py-6 border-b border-white/10 last:border-b-0">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {Icon && (
            <div className="p-2 bg-primary/10 rounded-lg">
              <Icon className="h-4 w-4 text-primary" />
            </div>
          )}
          <h3 className="text-lg font-semibold text-foreground">{title}</h3>
        </div>
        {onCopy && (
          <LiquidButton variant="ghost" size="sm" onClick={onCopy}>
            <CopyIcon className="h-4 w-4 mr-2" />
            Copy
          </LiquidButton>
        )}
      </div>
      <div className="prose prose-invert max-w-none text-muted-foreground leading-relaxed">
        {children}
      </div>
    </div>
  );
}

export function KnowledgeItemDetail() {
  const { itemId } = useParams<{ itemId: string }>();
  const navigate = useNavigate();
  const {
    currentKnowledgeItem: item,
    loadKnowledgeItem,
    loading,
    error,
  } = useKnowledgeStore();

  React.useEffect(() => {
    if (itemId) {
      loadKnowledgeItem(itemId);
    }
  }, [itemId, loadKnowledgeItem]);

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      // Could add a toast notification here
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  if (loading || !item) {
    return (
      <PageLayout>
        <div className="flex justify-center items-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout>
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </PageLayout>
    );
  }

  return (
    <PageLayout maxWidth="2xl" spacing="lg">
      <PageHeader
        title={item.display_title}
        actions={
          <LiquidButton variant="outline" onClick={() => navigate('/knowledge')}>
            <ArrowLeftIcon className="h-4 w-4 mr-2" />
            Back to Knowledge Base
          </LiquidButton>
        }
      >
        <ItemMetadata item={item} />
      </PageHeader>

      <PageContent layout="single" gap="lg">
        <GlassCard variant="primary" className="p-6">
          {item.summary && (
            <ContentSection 
              title="AI Summary" 
              onCopy={() => handleCopy(item.summary!)}
            >
              <p className="whitespace-pre-wrap">{item.summary}</p>
            </ContentSection>
          )}

          {item.enhanced_content && (
            <ContentSection 
              title="Enhanced Content" 
              onCopy={() => handleCopy(item.enhanced_content!)}
            >
              <div 
                className="prose prose-invert max-w-none" 
                dangerouslySetInnerHTML={{ __html: item.enhanced_content }} 
              />
            </ContentSection>
          )}

          {/* Additional content sections could be added here based on actual data structure */}
        </GlassCard>
      </PageContent>
    </PageLayout>
  );
}
