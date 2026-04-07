import { useState, useCallback } from 'react';
import { useApi, postApi } from '../hooks/useApi';
import TierBadge from './TierBadge';
import { CheckCircle, XCircle } from 'lucide-react';

export default function Approvals() {
  const { data, loading, error, refetch } = useApi('/approvals/pending');
  const [actionInFlight, setActionInFlight] = useState(null);

  const handleDecide = useCallback(async (id, decision) => {
    setActionInFlight(id);
    try {
      await postApi(`/approvals/${id}/decide`, { decision, decided_by: 'operator' });
      await refetch();
    } finally {
      setActionInFlight(null);
    }
  }, [refetch]);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h1 className="text-2xl font-bold">Pending Approvals</h1>

      {loading && <p className="text-slate-500">Loading...</p>}
      {error && <p className="text-red-600">Error: {error}</p>}

      {data && data.length === 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-400">
          No pending approvals. All clear.
        </div>
      )}

      {data && data.map(a => (
        <div key={a.approval_id} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center gap-3">
            <TierBadge tier={a.risk_tier} />
            <span className="font-semibold text-sm">{a.approval_id}</span>
            <span className="text-xs text-slate-400">Shipment {a.shipment_id}</span>
            <span className="ml-auto text-xs text-slate-400">{a.created_at}</span>
          </div>
          <p className="text-sm">{a.action_description}</p>
          <p className="text-xs text-slate-500">{a.justification}</p>
          <div className="text-xs">
            <span className="text-slate-500 uppercase tracking-wider">Proposed actions: </span>
            {a.proposed_actions.join(' -> ')}
          </div>
          <div className="flex gap-2 pt-2 border-t border-slate-100">
            <button
              onClick={() => handleDecide(a.approval_id, 'approved')}
              disabled={actionInFlight === a.approval_id}
              className="flex items-center gap-1.5 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium
                         hover:bg-green-700 disabled:opacity-50 transition"
            >
              <CheckCircle className="w-4 h-4" /> Approve
            </button>
            <button
              onClick={() => handleDecide(a.approval_id, 'rejected')}
              disabled={actionInFlight === a.approval_id}
              className="flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium
                         hover:bg-red-700 disabled:opacity-50 transition"
            >
              <XCircle className="w-4 h-4" /> Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
