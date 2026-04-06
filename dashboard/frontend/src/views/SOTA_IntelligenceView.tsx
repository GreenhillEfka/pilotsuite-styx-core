import React, { useEffect, useRef, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ExternalLink } from 'lucide-react';

interface TraceStep {
  id: string;
  stage: 'ingest' | 'retrieval' | 'reasoning' | 'execution';
  timestamp: number;
  content: string;
  source?: string;
  tokens?: number;
  model?: string;
}

interface StreamPayload {
  ok: boolean;
  trace_id: string | null;
  query: string;
  events: Array<{
    type: 'query_start' | 'trace_step';
    query?: string;
    step?: TraceStep;
  }>;
}

const IntelligenceView: React.FC = () => {
  const [traces, setTraces] = useState<TraceStep[]>([]);
  const [activeQuery, setActiveQuery] = useState('');
  const seenTraceRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const hydrateFromStream = async () => {
      try {
        const response = await fetch('/api/v1/backend/rag/trace/stream', {
          headers: { 'Accept': 'application/json' },
          cache: 'no-store',
        });

        if (!response.ok || cancelled) {
          return;
        }

        const payload = (await response.json()) as StreamPayload;
        if (!payload.ok) {
          return;
        }

        const incomingQuery = payload.query || '';
        const incomingSteps = payload.events
          .filter((evt) => evt.type === 'trace_step' && Boolean(evt.step))
          .map((evt) => evt.step as TraceStep)
          .filter(Boolean);

        if (payload.trace_id) {
          const sameTrace = seenTraceRef.current === payload.trace_id;

          setActiveQuery(incomingQuery);

          if (!sameTrace) {
            seenTraceRef.current = payload.trace_id;
            setTraces(incomingSteps);
          } else {
            setTraces((prev) => {
              const byId = new Set(prev.map((step) => step.id));
              const merged = [...prev];
              incomingSteps.forEach((step) => {
                if (!byId.has(step.id)) {
                  merged.push(step);
                  byId.add(step.id);
                }
              });
              return merged.slice(-30);
            });
          }
        } else if (seenTraceRef.current !== null) {
          seenTraceRef.current = null;
          setActiveQuery("");
          setTraces([]);
        }
      } catch (error) {
        if (!cancelled) {
          console.debug('RAG trace stream fetch failed', error);
        }
      }
    };

    void hydrateFromStream();
    const timer = window.setInterval(hydrateFromStream, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const getStageColor = (stage: string) => {
    switch (stage) {
      case 'ingest': return 'border-ps-brand-blue bg-ps-brand-blue/10';
      case 'retrieval': return 'border-ps-brand-gold bg-ps-brand-gold/10';
      case 'reasoning': return 'border-green-500 bg-green-500/10';
      default: return 'border-zinc-600 bg-zinc-800';
    }
  };

  const getStageBadge = (stage: string) => {
    const variants: Record<string, string> = {
      ingest: 'INGEST',
      retrieval: 'RETRIEVAL',
      reasoning: 'REASONING',
      execution: 'EXECUTION'
    };
    return variants[stage] || stage.toUpperCase();
  };

  return (
    <div className="p-6 space-y-6 bg-ps-bg-dark min-h-screen text-white">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Intelligence & RAG Trace</h1>
          {activeQuery && (
            <p className="text-ps-text-dim text-sm mt-1">
              Query: "{activeQuery}"
            </p>
          )}
        </div>
        <Badge variant="outline" className="text-ps-brand-blue">
          {traces.length} Steps
        </Badge>
      </div>

      <div className="space-y-3">
        {traces.map((step) => (
          <Card
            className={`border-l-4 ${getStageColor(step.stage)} bg-ps-card-dark border-zinc-800 transition-all hover:translate-x-1`}
            key={step.id}
          >
            <CardContent className="p-4">
              <div className="flex gap-4 items-start">
                <div className="flex flex-col items-center min-w-[80px]">
                  <span className={`text-[10px] font-mono px-2 py-1 rounded ${
                    step.stage === 'ingest' ? 'bg-ps-brand-blue/20 text-ps-brand-blue' :
                    step.stage === 'retrieval' ? 'bg-ps-brand-gold/20 text-ps-brand-gold' :
                    'bg-green-500/20 text-green-500'
                  }`}>
                    {getStageBadge(step.stage)}
                  </span>
                  <span className="text-[10px] text-ps-text-dim mt-1">
                    T+{step.timestamp}ms
                  </span>
                </div>

                <div className="flex-1 space-y-2">
                  <p className="text-sm text-zinc-200">{step.content}</p>

                  {step.tokens !== undefined && (
                    <span className="text-[10px] text-ps-text-dim">
                      Tokens: {step.tokens}
                    </span>
                  )}

                  {step.source && (
                    <div className="mt-2 p-2 bg-zinc-900/50 rounded border border-white/5 flex justify-between items-center group cursor-pointer hover:border-ps-brand-blue transition-colors">
                      <span className="text-[10px] text-zinc-400 truncate">
                        Source: {step.source}
                      </span>
                      <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 text-ps-brand-blue" />
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {traces.length === 0 && (
          <div className="text-center py-12 text-ps-text-dim">
            <p>Waiting for RAG query...</p>
            <p className="text-xs mt-2 opacity-50">Trace will appear here when a semantic search is executed</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default IntelligenceView;
