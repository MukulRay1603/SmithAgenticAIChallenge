import { useState, useCallback } from 'react';
import { useApi, postApi } from '../hooks/useApi';
import TierBadge from './TierBadge';
import { Play, Zap, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';

export default function AgentActivity() {
  const { data: history, loading, refetch } = useApi('/orchestrator/history?limit=30');
  const { data: overview } = useApi('/risk/overview');
  const [running, setRunning] = useState(false);
  const [expanded, setExpanded] = useState(null);

  const runCriticalBatch = useCallback(async () => {
    setRunning(true);
    try {
      const windows = await (await fetch('/api/windows?risk_tier=CRITICAL&limit=5')).json();
      const ids = windows.map(w => w.window_id);
      if (ids.length > 0) {
        await postApi('/orchestrator/run-batch', ids);
        await refetch();
      }
    } finally {
      setRunning(false);
    }
  }, [refetch]);

  const runSingle = useCallback(async (windowId) => {
    setRunning(true);
    try {
      await postApi(`/orchestrator/run/${windowId}`, {});
      await refetch();
    } finally {
      setRunning(false);
    }
  }, [refetch]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Agent Activity</h1>
        <div className="flex gap-2">
          <button onClick={runCriticalBatch} disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition">
            <Zap className="w-4 h-4" />
            {running ? 'Running...' : 'Orchestrate Top 5 CRITICAL'}
          </button>
        </div>
      </div>

      {/* Quick run panel */}
      <QuickRunPanel onRun={runSingle} running={running} />

      {loading && <p className="text-slate-500">Loading history...</p>}

      {history && history.length === 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-400">
          No orchestration decisions yet. Click the button above to run the agent on CRITICAL windows.
        </div>
      )}

      {history && history.map((dec, i) => (
        <DecisionCard key={i} decision={dec} index={i}
          expanded={expanded === i} onToggle={() => setExpanded(expanded === i ? null : i)} />
      ))}
    </div>
  );
}

function QuickRunPanel({ onRun, running }) {
  const [windowId, setWindowId] = useState('');
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex items-center gap-3">
      <span className="text-sm text-slate-500 font-medium">Run orchestrator on:</span>
      <input value={windowId} onChange={e => setWindowId(e.target.value)}
        placeholder="e.g. W01205"
        className="border border-slate-300 rounded-md px-3 py-1.5 text-sm w-32" />
      <button onClick={() => windowId && onRun(windowId)} disabled={running || !windowId}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition">
        <Play className="w-3.5 h-3.5" /> Run
      </button>
    </div>
  );
}

function DecisionCard({ decision, index, expanded, onToggle }) {
  const d = decision;
  const actionsCount = (d.actions_taken || []).length;
  const hasErrors = actionsCount === 0 && d.risk_tier !== 'LOW';

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-3 cursor-pointer hover:bg-slate-50 transition" onClick={onToggle}>
        <TierBadge tier={d.risk_tier} />
        <span className="font-mono text-sm font-semibold">{d.window_id || d._window_id}</span>
        <span className="text-xs text-slate-400">{d.shipment_id} / {d.container_id}</span>
        <span className="text-xs text-slate-500 ml-auto flex items-center gap-2">
          {actionsCount > 0 && (
            <span className="flex items-center gap-1 text-green-600">
              <CheckCircle className="w-3.5 h-3.5" /> {actionsCount} tools
            </span>
          )}
          {d.requires_approval && (
            <span className="flex items-center gap-1 text-amber-600">
              <Zap className="w-3.5 h-3.5" /> Needs approval
            </span>
          )}
          <span className="font-mono">conf: {(d.confidence || 0).toFixed(2)}</span>
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </span>
      </div>

      {expanded && (
        <div className="px-5 pb-5 pt-2 border-t border-slate-100 space-y-4">
          {/* Summary */}
          <p className="text-sm text-slate-700">{d.decision_summary}</p>

          {/* Draft plan */}
          {d.draft_plan?.length > 0 && (
            <PlanSection title="Draft Plan" steps={d.draft_plan} />
          )}

          {/* Reflection */}
          {d.reflection_notes?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Reflection Notes</p>
              {d.reflection_notes.map((n, j) => (
                <p key={j} className={`text-xs ${n.includes('GAP') ? 'text-amber-700' : 'text-green-700'}`}>{n}</p>
              ))}
            </div>
          )}

          {/* Revised plan */}
          {d.revised_plan?.length > 0 && (
            <PlanSection title="Revised Plan" steps={d.revised_plan} />
          )}

          {/* Actions taken */}
          {d.actions_taken?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Actions Taken</p>
              {d.actions_taken.map((a, j) => (
                <div key={j} className="bg-slate-50 rounded-lg p-3 mb-2 text-xs">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-indigo-700">{a.tool}</span>
                    {a.result?.status && (
                      <span className="text-green-600">{a.result.status}</span>
                    )}
                  </div>
                  <pre className="text-[10px] text-slate-500 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(a.result, null, 2).slice(0, 500)}
                  </pre>
                </div>
              ))}
            </div>
          )}

          {/* Fallback */}
          {d.fallback_plan?.length > 0 && (
            <PlanSection title="Fallback Plan" steps={d.fallback_plan} />
          )}

          {/* Approval */}
          {d.approval_id && (
            <p className="text-xs text-amber-700 font-medium">
              Approval ID: {d.approval_id} -- {d.approval_reason}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function PlanSection({ title, steps }) {
  return (
    <div>
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">{title}</p>
      <div className="space-y-1">
        {steps.map((s, i) => (
          <div key={i} className="flex gap-2 text-xs">
            <span className="font-mono text-slate-400 w-5 text-right">{s.step}.</span>
            <span className="text-slate-700">{s.action}</span>
            <span className="text-slate-400 ml-auto italic">{s.reason?.slice(0, 60)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
