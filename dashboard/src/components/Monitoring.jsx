import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import { Link } from 'react-router-dom';
import { Activity, AlertTriangle, ThermometerSun, Clock } from 'lucide-react';
import TierBadge from './TierBadge';

const TIER_BG = {
  CRITICAL: 'bg-red-50 border-red-200',
  HIGH: 'bg-orange-50 border-orange-200',
  MEDIUM: 'bg-yellow-50 border-yellow-200',
  LOW: 'bg-white border-slate-200',
};

export default function Monitoring() {
  const [feed, setFeed] = useState([]);
  const [page, setPage] = useState(0);
  const { data: overview } = useApi('/risk/overview');

  const loadMore = useCallback(async () => {
    const res = await fetch(`/api/windows?limit=30&offset=${page * 30}`);
    const rows = await res.json();
    setFeed(prev => page === 0 ? rows : [...prev, ...rows]);
  }, [page]);

  useEffect(() => { loadMore(); }, [loadMore]);

  const criticals = feed.filter(w => w.risk_tier === 'CRITICAL');
  const highs = feed.filter(w => w.risk_tier === 'HIGH');

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Live Monitoring</h1>

      {/* KPI strip */}
      {overview && (
        <div className="grid grid-cols-6 gap-3">
          <KPI icon={Activity} label="Active Windows" value={overview.total_windows.toLocaleString()} color="bg-blue-600" />
          <KPI icon={AlertTriangle} label="Critical" value={overview.tier_counts.CRITICAL || 0} color="bg-red-600" />
          <KPI icon={AlertTriangle} label="High" value={overview.tier_counts.HIGH || 0} color="bg-orange-500" />
          <KPI icon={ThermometerSun} label="Medium" value={overview.tier_counts.MEDIUM || 0} color="bg-yellow-500" />
          <KPI icon={Clock} label="Low" value={overview.tier_counts.LOW || 0} color="bg-green-600" />
          <KPI icon={Activity} label="Shipments" value={overview.total_shipments} color="bg-indigo-600" />
        </div>
      )}

      {/* Alert banner */}
      {criticals.length > 0 && (
        <div className="bg-red-600 text-white rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-6 h-6 animate-pulse" />
          <div>
            <p className="font-semibold">{criticals.length} CRITICAL windows in current view</p>
            <p className="text-sm text-red-100">Immediate action required for these shipments.</p>
          </div>
        </div>
      )}

      {/* Live feed */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
          <h2 className="text-sm font-semibold text-slate-600">Risk Feed (sorted by score)</h2>
        </div>
        <div className="divide-y divide-slate-100 max-h-[600px] overflow-y-auto">
          {feed.map(w => (
            <div key={w.window_id}
              className={`px-4 py-3 flex items-center gap-4 hover:bg-slate-50/50 transition border-l-4 ${
                w.risk_tier === 'CRITICAL' ? 'border-l-red-500 bg-red-50/30' :
                w.risk_tier === 'HIGH' ? 'border-l-orange-400 bg-orange-50/20' :
                w.risk_tier === 'MEDIUM' ? 'border-l-yellow-400' : 'border-l-transparent'
              }`}>
              <TierBadge tier={w.risk_tier} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold">{w.window_id}</span>
                  <Link to={`/shipments/${w.shipment_id}`}
                    className="text-xs text-blue-600 hover:underline">{w.shipment_id}</Link>
                  <span className="text-xs text-slate-400">{w.container_id} / {w.product_id}</span>
                </div>
                <div className="flex items-center gap-4 mt-0.5 text-xs text-slate-500">
                  <span>Temp: <span className="font-mono font-medium">{w.avg_temp_c.toFixed(1)}C</span></span>
                  <span>Phase: {w.transit_phase}</span>
                  {w.det_rules_fired && (
                    <span className="text-orange-600">{w.det_rules_fired}</span>
                  )}
                </div>
              </div>
              <div className="text-right">
                <p className="font-mono text-sm font-bold">{w.final_score.toFixed(4)}</p>
                <p className="text-[10px] text-slate-400">D:{w.det_score.toFixed(2)} ML:{w.ml_score.toFixed(2)}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="px-4 py-3 border-t border-slate-200 text-center">
          <button onClick={() => setPage(p => p + 1)}
            className="text-sm text-blue-600 hover:underline font-medium">
            Load more windows
          </button>
        </div>
      </div>
    </div>
  );
}

function KPI({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-3 flex items-center gap-3 shadow-sm">
      <div className={`rounded-lg p-2 ${color}`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
      <div>
        <p className="text-[10px] text-slate-500 uppercase tracking-wide leading-tight">{label}</p>
        <p className="text-lg font-bold leading-tight">{value}</p>
      </div>
    </div>
  );
}
