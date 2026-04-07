import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import TierBadge from './TierBadge';

const TIERS = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

export default function ShipmentList() {
  const [filter, setFilter] = useState('ALL');
  const path = filter === 'ALL' ? '/shipments' : `/shipments?risk_tier=${filter}`;
  const { data, loading, error } = useApi(path, [filter]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Shipments</h1>
        <div className="flex gap-1">
          {TIERS.map(t => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition
                ${filter === t ? 'bg-slate-800 text-white' : 'bg-white border border-slate-300 text-slate-600 hover:bg-slate-100'}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="text-slate-500">Loading...</p>}
      {error && <p className="text-red-600">Error: {error}</p>}

      {data && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr className="text-left text-xs text-slate-500 uppercase tracking-wider">
                <th className="px-4 py-3">Shipment</th>
                <th className="px-4 py-3">Containers</th>
                <th className="px-4 py-3">Products</th>
                <th className="px-4 py-3">Windows</th>
                <th className="px-4 py-3">Risk Tier</th>
                <th className="px-4 py-3">Max Score</th>
                <th className="px-4 py-3">% Critical</th>
                <th className="px-4 py-3">% High</th>
              </tr>
            </thead>
            <tbody>
              {data.map(s => (
                <tr key={s.shipment_id} className="border-t border-slate-100 hover:bg-blue-50/40 transition">
                  <td className="px-4 py-3">
                    <Link to={`/shipments/${s.shipment_id}`} className="text-blue-600 hover:underline font-medium">
                      {s.shipment_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{s.containers.join(', ')}</td>
                  <td className="px-4 py-3 text-slate-600">{s.products.join(', ')}</td>
                  <td className="px-4 py-3">{s.total_windows}</td>
                  <td className="px-4 py-3"><TierBadge tier={s.latest_risk_tier} /></td>
                  <td className="px-4 py-3 font-mono">{s.max_fused_score.toFixed(4)}</td>
                  <td className="px-4 py-3">{s.pct_critical}%</td>
                  <td className="px-4 py-3">{s.pct_high}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
