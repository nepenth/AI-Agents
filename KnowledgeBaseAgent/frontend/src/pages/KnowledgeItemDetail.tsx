import * as React from 'react';
import { useParams } from 'react-router-dom';
import { useKnowledgeStore } from '@/stores';
import { GlassCard } from '@/components/ui/GlassCard';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { ExternalLinkIcon } from 'lucide-react';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="py-6 border-b border-white/10 last:border-b-0">
      <h3 className="text-lg font-semibold text-foreground mb-3">{title}</h3>
      <div className="prose prose-invert max-w-none text-muted-foreground">
        {children}
      </div>
    </div>
  );
}

export function KnowledgeItemDetail() {
  const { itemId } = useParams<{ itemId: string }>();
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

  if (loading || !item) {
    return <div className="flex justify-center items-center h-64"><LoadingSpinner /></div>;
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  // Assuming `item.raw_data` holds the original tweet info, based on design docs.
  const originalTweetUrl = `https://twitter.com/user/status/${item.source_id}`;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-foreground">{item.display_title}</h2>
        <div className="text-sm text-muted-foreground mt-2">
          <span>{item.main_category} / {item.sub_category}</span>
          <a href={originalTweetUrl} target="_blank" rel="noopener noreferrer" className="ml-4 inline-flex items-center gap-1 hover:text-primary">
            View Original <ExternalLinkIcon className="h-3 w-3" />
          </a>
        </div>
      </div>

      <GlassCard>
        {item.summary && (
          <Section title="AI Summary">
            <p>{item.summary}</p>
          </Section>
        )}

        {item.enhanced_content && (
          <Section title="Enhanced Content">
            {/* This could be rendered as markdown in a real scenario */}
            <p>{item.enhanced_content}</p>
          </Section>
        )}

        {item.content_item?.raw_data && (
           <Section title="Original Content">
             <blockquote className="border-l-2 border-muted pl-4 italic">
              {item.content_item.raw_data.text}
             </blockquote>
           </Section>
        )}
      </GlassCard>
    </div>
  );
}
