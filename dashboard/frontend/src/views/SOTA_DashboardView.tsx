import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const DashboardView: React.FC = () => {
  const [metrics, setMetrics] = useState<any>([]);
  const [health, setHealth] = useState('Healthy');

  // WebSocket connection for real-time KPI streaming (Slice 145)
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/api/v1/backend/dashboard/stream');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMetrics((prev: any) => [...prev.slice(-20), data]);
      if (data.anomaly_score > 50) setHealth('Healing');
    };
    return () => ws.close();
  }, []);

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
            <div className="text-2xl font-mono text-ps-brand-blue">42ms</div>
          </CardContent>
        </Card>
        <Card className="bg-ps-card-dark border-zinc-800">
          <CardHeader><CardTitle className="text-sm">Token Burn / min</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-mono text-ps-brand-gold">1.2k</div>
          </CardContent>
        </Card>
        <Card className="bg-ps-card-dark border-zinc-800">
          <CardHeader><CardTitle className="text-sm">Anomaly Score</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-mono text-ps-brand-red">0.04</div>
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
