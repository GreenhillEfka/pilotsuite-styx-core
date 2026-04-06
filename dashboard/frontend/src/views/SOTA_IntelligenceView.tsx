import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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

const IntelligenceView: React.FC = () => {
  const [traces, setTraces] = useState<TraceStep[]>([]);
  const [activeQuery, setActiveQuery] = useState('');

  // WebSocket for RAG trace stream (Slice 140)
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/api/v1/backend/rag/trace/stream');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'query_start') {
        setActiveQuery(data.query);
        setTraces([]);
      } else if (data.type === 'trace_step') {
        setTraces((prev) => [...prev, data.step]);
      }
    };
    return () => ws.close();
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
        {traces.map((step, idx) => (
          <Card
            key={step.id}
            className={`border-l-4 ${getStageColor(step.stage)} bg-ps-card-dark border-zinc-800 transition-all hover:translate-x-1`}
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

                  {step.tokens && (
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
