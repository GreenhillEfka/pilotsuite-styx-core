import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Link2, Unlink, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';

interface ZoneLink {
  id: string;
  ha_area: string;
  core_habitus: string;
  confidence: number;
  status: 'synced' | 'drift' | 'orphan';
}

const ZonesView: React.FC = () => {
  const [links, setLinks] = useState<ZoneLink[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);

  // Initial fetch for zone truth (Slice 147)
  useEffect(() => {
    fetch('/api/v1/zone_automation/truth/zones')
      .then(res => res.json())
      .then(data => setLinks(data.links || []));
  }, []);

  const handleManualSync = () => {
    setIsSyncing(true);
    setTimeout(() => setIsSyncing(false), 1500); // Simulate sync
  };

  return (
    <div className="p-6 space-y-6 bg-ps-bg-dark min-h-screen text-white">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Zones & Symbiosis Mapper</h1>
          <p className="text-ps-text-dim text-sm mt-1">HA Areas ↔ PilotSuite Habitus Sync Status</p>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          onClick={handleManualSync}
          disabled={isSyncing}
          className="border-ps-brand-blue text-ps-brand-blue hover:bg-ps-brand-blue/10"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${isSyncing ? 'animate-spin' : ''}`} />
          Run Zero-Config Reconciler
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {links.map((link) => (
          <Card key={link.id} className="bg-ps-card-dark border-zinc-800 hover:border-zinc-700 transition-all">
            <CardContent className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-8 flex-1">
                {/* HA Source */}
                <div className="w-1/3">
                  <span className="text-[10px] text-ps-text-dim block mb-1">HA AREA</span>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-ps-brand-blue" />
                    <span className="font-medium">{link.ha_area}</span>
                  </div>
                </div>

                {/* Link Indicator */}
                <div className="flex flex-col items-center">
                  <div className={`p-2 rounded-full ${link.status === 'synced' ? 'bg-green-500/10 text-green-500' : 'bg-ps-brand-gold/10 text-ps-brand-gold'}`}>
                    {link.status === 'synced' ? <Link2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                  </div>
                  <span className="text-[10px] mt-1 font-mono">{Math.round(link.confidence * 100)}%</span>
                </div>

                {/* Core Habitus */}
                <div className="w-1/3">
                  <span className="text-[10px] text-ps-text-dim block mb-1">PILOTSUITE HABITUS</span>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-ps-brand-gold" />
                    <span className="font-medium text-ps-brand-gold">{link.core_habitus}</span>
                  </div>
                </div>
              </div>

              <div className="flex gap-2">
                <Button size="icon" variant="ghost" className="text-ps-text-dim hover:text-white">
                  <CheckCircle2 className="w-4 h-4" />
                </Button>
                <Button size="icon" variant="ghost" className="text-ps-text-dim hover:text-red-400">
                  <Unlink className="w-4 h-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}

        {links.length === 0 && (
          <div className="text-center py-12 border-2 border-dashed border-zinc-800 rounded-lg">
            <p className="text-ps-text-dim">No zone mappings found.</p>
            <Button size="sm" className="mt-4 bg-ps-brand-blue hover:bg-ps-brand-blue/80" onClick={handleManualSync}>
              Run Initial Discovery
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ZonesView;
