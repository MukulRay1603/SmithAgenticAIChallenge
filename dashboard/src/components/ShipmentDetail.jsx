import { useParams, Link } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine,
} from 'recharts';
import { ArrowLeft } from 'lucide-react';
import TierBadge from './TierBadge';

const TIER_COLORS = { CRITICAL: '#dc2626', HIGH: '#ea580c', MEDIUM: '#ca8a04', LOW: '#16a34a' };

export default function ShipmentDetail() {
  const { id } = useParams();
  const { data: windows, loading, error } = useApi(`/shipments/${id}/windows`);

  if (loading) return <div className="p-8 text-slate-500">Loading...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  const chartData = windows.map((w, i) => ({
    idx: i,
    temp: w.avg_temp_c,
    final: w.final_score,
    det: w.det_score,
    ml: w.ml_score,
    tier: w.risk_tier,
    wid: w.window_id,
    phase: w.transit_phase,
  }));

  const critCount = windows.filter(w => w.risk_tier === 'CRITICAL').length;
  const highCount = windows.filter(w => w.risk_tier === 'HIGH').length;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/shipments" className="text-slate-400 hover:text-slate-700"><ArrowLeft className="w-5 h-5" /></Link>
        <h1 className="text-2xl font-bold">{id}</h1>
        <span className="text-sm text-slate-500">{windows.length} windows</span>
        {critCount > 0 && <TierBadge tier="CRITICAL" />}
        {highCount > 0 && <TierBadge tier="HIGH" />}
      </div>

      {/* Temperature timeline */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-600 mb-3">Temperature Timeline</h2>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="idx" tick={{ fontSize: 10 }} label={{ value: 'Window index', position: 'bottom', fontSize: 11 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip
              content={({ payload }) => {
                if (!payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="bg-white border rounded-lg p-2 text-xs shadow-lg">
                    <p className="font-semibold">{d.wid}</p>
                    <p>Temp: {d.temp.toFixed(2)} C</p>
                    <p>Phase: {d.phase}</p>
                  </div>
                );
              }}
            />
            <Line type="monotone" dataKey="temp" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Risk score timeline */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-600 mb-3">Risk Score Timeline</h2>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="idx" tick={{ fontSize: 10 }} />
            <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} />
            <Tooltip
              content={({ payload }) => {
                if (!payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="bg-white border rounded-lg p-2 text-xs shadow-lg">
                    <p className="font-semibold">{d.wid} <TierBadge tier={d.tier} /></p>
                    <p>Final: {d.final.toFixed(4)}</p>
                    <p>Det: {d.det.toFixed(4)} / ML: {d.ml.toFixed(4)}</p>
                  </div>
                );
              }}
            />
            <ReferenceLine y={0.8} stroke="#dc2626" strokeDasharray="4 4" label="Critical" />
            <ReferenceLine y={0.6} stroke="#ea580c" strokeDasharray="4 4" label="High" />
            <ReferenceLine y={0.3} stroke="#ca8a04" strokeDasharray="4 4" label="Medium" />
            <Line type="monotone" dataKey="final" stroke="#6366f1" strokeWidth={2} dot={false} name="Fused" />
            <Line type="monotone" dataKey="det" stroke="#f97316" strokeWidth={1} dot={false} opacity={0.5} name="Deterministic" />
            <Line type="monotone" dataKey="ml" stroke="#10b981" strokeWidth={1} dot={false} opacity={0.5} name="ML" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Window table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-50">
              <tr className="text-left text-slate-500 uppercase tracking-wider">
                <th className="px-3 py-2">Window</th>
                <th className="px-3 py-2">Container</th>
                <th className="px-3 py-2">Product</th>
                <th className="px-3 py-2">Phase</th>
                <th className="px-3 py-2">Temp (C)</th>
                <th className="px-3 py-2">Det Score</th>
                <th className="px-3 py-2">ML Score</th>
                <th className="px-3 py-2">Final</th>
                <th className="px-3 py-2">Tier</th>
                <th className="px-3 py-2">Rules Fired</th>
              </tr>
            </thead>
            <tbody>
              {windows.map(w => (
                <tr key={w.window_id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-1.5 font-mono">{w.window_id}</td>
                  <td className="px-3 py-1.5">{w.container_id}</td>
                  <td className="px-3 py-1.5">{w.product_id}</td>
                  <td className="px-3 py-1.5">{w.transit_phase}</td>
                  <td className="px-3 py-1.5 font-mono">{w.avg_temp_c.toFixed(2)}</td>
                  <td className="px-3 py-1.5 font-mono">{w.det_score.toFixed(4)}</td>
                  <td className="px-3 py-1.5 font-mono">{w.ml_score.toFixed(4)}</td>
                  <td className="px-3 py-1.5 font-mono font-semibold">{w.final_score.toFixed(4)}</td>
                  <td className="px-3 py-1.5"><TierBadge tier={w.risk_tier} /></td>
                  <td className="px-3 py-1.5 text-slate-500 max-w-[200px] truncate">{w.det_rules_fired || '--'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
