import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import TierBadge from './TierBadge';

export default function AuditLog() {
  const [tierFilter, setTierFilter] = useState('');
  const path = tierFilter ? `/audit-logs?limit=200&risk_tier=${tierFilter}` : '/audit-logs?limit=200';
  const { data, loading, error } = useApi(path, [tierFilter]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Compliance Audit Log</h1>
        <select
          value={tierFilter}
          onChange={e => setTierFilter(e.target.value)}
          className="border border-slate-300 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">All tiers</option>
          <option value="CRITICAL">CRITICAL</option>
          <option value="HIGH">HIGH</option>
          <option value="MEDIUM">MEDIUM</option>
          <option value="LOW">LOW</option>
        </select>
      </div>

      {loading && <p className="text-slate-500">Loading...</p>}
      {error && <p className="text-red-600">Error: {error}</p>}

      {data && (
        <div className="space-y-3">
          {data.map((rec, i) => (
            <div key={i} className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
              <div className="flex items-center gap-3 mb-2">
                <TierBadge tier={rec.risk_tier} />
                <span className="font-mono text-sm font-semibold">{rec.window_id}</span>
                <span className="text-xs text-slate-400">{rec.shipment_id} / {rec.container_id}</span>
                <span className="text-xs text-slate-400 ml-auto">{rec.assessment_timestamp}</span>
              </div>
              <div className="grid grid-cols-4 gap-4 text-xs">
                <div>
                  <p className="text-slate-500 uppercase tracking-wider mb-0.5">Scores</p>
                  <p>Det: <span className="font-mono font-medium">{rec.deterministic_score?.toFixed(4)}</span></p>
                  <p>ML: <span className="font-mono font-medium">{rec.ml_score?.toFixed(4)}</span></p>
                  <p>Final: <span className="font-mono font-semibold">{rec.final_score?.toFixed(4)}</span></p>
                </div>
                <div>
                  <p className="text-slate-500 uppercase tracking-wider mb-0.5">Rules Fired</p>
                  {rec.deterministic_rules_fired?.length > 0
                    ? rec.deterministic_rules_fired.map((r, j) => <p key={j} className="text-orange-700">{r}</p>)
                    : <p className="text-slate-400">none</p>}
                </div>
                <div>
                  <p className="text-slate-500 uppercase tracking-wider mb-0.5">Top ML Features</p>
                  {(rec.ml_top_features || []).slice(0, 3).map((f, j) => (
                    <p key={j}>{f.feature}: <span className="font-mono">{f.shap_value?.toFixed(3)}</span></p>
                  ))}
                </div>
                <div>
                  <p className="text-slate-500 uppercase tracking-wider mb-0.5">Actions</p>
                  {rec.recommended_actions?.map((a, j) => <p key={j} className="text-blue-700">{a}</p>)}
                  {rec.requires_human_approval && (
                    <p className="text-red-600 font-semibold mt-1">Requires human approval</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
