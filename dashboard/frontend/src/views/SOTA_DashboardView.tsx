import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface DashboardPoint {
  time: string;
  ops: number;
  latencyMs: number;
  anomaly_score: number;
}

const DashboardView: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardPoint[]>([]);
  const [health, setHealth] = useState('Healthy');

  const normalizePoint = (payload: any): DashboardPoint => {
    const ops = Number(payload?.ops ?? payload?.raw?.gauges?.ops_per_min ?? 0) || 0;
    const latencyMs = Number(payload?.latency_ms ?? payload?.raw?.gauges?.p95_latency_ms ?? 0) || 0;
    const anomaly = Number(payload?.anomaly_score ?? 0) || 0;

    return {
      time: payload?.time || new Date().toISOString(),
      ops,
      latencyMs,
      anomaly_score: anomaly,
    };
  };

  useEffect(() => {
    let active = true;

    const fetchStream = async () => {
      try {
        const response = await fetch('/api/v1/backend/dashboard/stream', {
          headers: { 'Accept': 'application/json' },
          cache: 'no-store',
        });
        if (!response.ok || !active) {
          return;
        }

        const payload = await response.json();
        const point = normalizePoint(payload);

        if (active) {
          setMetrics((prev) => [...prev.slice(-19), point]);
          setHealth(point.anomaly_score > 50 ? 'Healing' : 'Healthy');
        }
      } catch (error) {
        // Keep UI stable when endpoint is unavailable
        if (active) {
          setHealth('Healing');
          console.debug('Dashboard stream fetch failed', error);
        }
      }
    };

    void fetchStream();
    const timer = window.setInterval(fetchStream, 2500);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const latest = metrics[metrics.length - 1];

  return (
    <div className="p-6 space-y-6 bg-ps-bg-dark min-h-screen text-white">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">PilotSuite SOTA Dashboard</h1>
        <Badge variant={health === 'Healthy' ? 'success' : 'warning'}>{health}</Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-ps-card-dark border-zinc-800">
          <CardHeader><CardTitle className="text-sm">API Latency (p95)</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-mono text-ps-brand-blue">{latest ? `${latest.latencyMs.toFixed(0)}ms` : '—'}</div>
          </CardContent>
        </Card>
        <Card className="bg-ps-card-dark border-zinc-800">
          <CardHeader><CardTitle className="text-sm">Ops / min</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-mono text-ps-brand-gold">{latest ? `${latest.ops.toFixed(0)}` : '—'}</div>
          </CardContent>
        </Card>
        <Card className="bg-ps-card-dark border-zinc-800">
          <CardHeader><CardTitle className="text-sm">Anomaly Score</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-mono text-ps-brand-red">{latest ? latest.anomaly_score.toFixed(2) : '—'}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-ps-card-dark border-zinc-800 h-64">
        <CardHeader><CardTitle className="text-sm text-ps-text-dim">System Throughput (Ops/min)</CardTitle></CardHeader>
        <CardContent className="h-full pb-12">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={metrics}>
              <XAxis dataKey="time" hide />
              <YAxis hide domain={['auto', 'auto']} />
              <Tooltip contentStyle={{ backgroundColor: '#18181b', border: 'none' }} />
              <Line type="monotone" dataKey="ops" stroke="#3b82f6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
};

export default DashboardView;
