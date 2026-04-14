import { useState, useCallback } from 'react';
import { useApi, postApi } from '../hooks/useApi';
import TierBadge from './TierBadge';
import { Play, Zap, CheckCircle, ChevronDown, ChevronUp, Building2, DollarSign, Shield } from 'lucide-react';

// ── Suitability tier badge ────────────────────────────────────────────

const SUITABILITY_COLORS = {
  ideal:       'bg-green-100 text-green-800',
  good:        'bg-blue-100 text-blue-800',
  acceptable:  'bg-yellow-100 text-yellow-800',
  last_resort: 'bg-orange-100 text-orange-800',
  disqualified:'bg-red-100 text-red-800',
};

function SuitabilityBadge({ tier }) {
  if (!tier) return null;
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${SUITABILITY_COLORS[tier] || 'bg-slate-100 text-slate-600'}`}>
      {tier}
    </span>
  );
}

// ── Routing decision badge ────────────────────────────────────────────

const ROUTING_COLORS = {
  primary:           'bg-green-100 text-green-800',
  backup:            'bg-blue-100 text-blue-800',
  split:             'bg-purple-100 text-purple-800',
  no_feasible_option:'bg-red-100 text-red-800',
};

function RoutingBadge({ decision }) {
  if (!decision) return null;
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${ROUTING_COLORS[decision] || 'bg-slate-100 text-slate-600'}`}>
      {decision.replace(/_/g, ' ')}
    </span>
  );
}

// ── Priority tier badge ───────────────────────────────────────────────

const PRIORITY_COLORS = {
  critical: 'bg-red-100 text-red-800',
  high:     'bg-orange-100 text-orange-800',
  medium:   'bg-yellow-100 text-yellow-800',
  routine:  'bg-slate-100 text-slate-600',
};

function PriorityBadge({ tier }) {
  if (!tier) return null;
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${PRIORITY_COLORS[tier] || 'bg-slate-100 text-slate-600'}`}>
      {tier}
    </span>
  );
}

// ── Per-tool structured result rendering ─────────────────────────────

function KV({ label, value, mono = false }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="flex items-start gap-1.5">
      <span className="text-slate-400 shrink-0">{label}:</span>
      <span className={`text-slate-700 ${mono ? 'font-mono' : ''}`}>{String(value)}</span>
    </div>
  );
}

function ColdStorageResult({ r }) {
  const alts = r.alternative_facilities || [];
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <Building2 className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
        <span className="font-semibold text-slate-800">{r.recommended_facility || '—'}</span>
        <SuitabilityBadge tier={r.suitability_tier} />
        {r.suitability_score != null && (
          <span className="text-[10px] text-slate-400 font-mono">score {r.suitability_score.toFixed(3)}</span>
        )}
      </div>
      {r.all_candidates_disqualified && (
        <p className="text-[10px] text-red-600 font-medium">⚠ All candidates disqualified — best available selected</p>
      )}
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px]">
        <KV label="Location"       value={r.location} />
        <KV label="Temp range"     value={r.temp_range_supported} mono />
        <KV label="Advance notice" value={r.advance_notice_required_hours != null ? `${r.advance_notice_required_hours}h required` : null} />
        <KV label="Transfer window" value={r.transfer_window_hours != null ? `${r.transfer_window_hours}h` : null} />
        <KV label="Capacity avail" value={r.available_capacity_pct != null ? `${r.available_capacity_pct.toFixed(0)}%` : null} />
        <KV label="Contact"        value={r.contact} />
      </div>
      {alts.length > 0 && (
        <div className="mt-1">
          <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider mb-1">
            Alternatives ({alts.length})
          </p>
          {alts.map((a, i) => (
            <div key={i} className="flex items-center gap-2 text-[11px] py-0.5">
              <span className="text-slate-600 truncate flex-1">{a.name}</span>
              {a.disqualified
                ? <span className="text-red-500 text-[10px]">✕ {a.disqualification_reason?.replace(/_/g, ' ')}</span>
                : <SuitabilityBadge tier={a.suitability_tier} />
              }
            </div>
          ))}
        </div>
      )}
      {r.selection_rationale && (
        <p className="text-[10px] text-slate-400 italic leading-snug">{r.selection_rationale}</p>
      )}
    </div>
  );
}

function SchedulingResult({ r }) {
  const flags = r.compliance_flags || {};
  const flagKeys = typeof flags === 'object' && !Array.isArray(flags)
    ? Object.keys(flags)
    : (Array.isArray(flags) ? flags : []);
  return (
    <div className="space-y-2">
      {r.summary_line && (
        <p className="text-[11px] text-slate-700 font-medium leading-snug">{r.summary_line}</p>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        <RoutingBadge decision={r.routing_decision} />
        <PriorityBadge tier={r.priority_tier} />
        {r.financial_impact_estimate_usd != null && (
          <span className="flex items-center gap-1 text-[11px] text-slate-600">
            <DollarSign className="w-3 h-3" />{r.financial_impact_estimate_usd.toLocaleString()} est. impact
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px]">
        <KV label="Routing"     value={r.routing_summary} />
        <KV label="Appts"       value={r.total_appointments_affected} />
        <KV label="Delay class" value={r.delay_class} />
        <KV label="Hours to breach" value={r.hours_to_breach != null ? `${r.hours_to_breach}h` : null} />
        <KV label="Spoilage prob" value={r.ml_spoilage_probability != null ? `${(r.ml_spoilage_probability * 100).toFixed(0)}%` : null} />
        <KV label="Priority score" value={r.priority_score?.toFixed(3)} mono />
      </div>
      {flagKeys.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
          <Shield className="w-3 h-3 text-amber-600 shrink-0" />
          {flagKeys.map(f => (
            <span key={f} className="text-[10px] bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded border border-amber-200">
              {f.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
      {r.actions_required?.length > 0 && (
        <ul className="text-[10px] text-slate-500 space-y-0.5 mt-1">
          {r.actions_required.slice(0, 4).map((act, i) => (
            <li key={i} className="flex gap-1"><span className="text-slate-300">›</span>{act}</li>
          ))}
          {r.actions_required.length > 4 && (
            <li className="text-slate-400">+{r.actions_required.length - 4} more</li>
          )}
        </ul>
      )}
    </div>
  );
}

function InsuranceResult({ r }) {
  const lb = r.loss_breakdown || {};
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <DollarSign className="w-3.5 h-3.5 text-green-600 shrink-0" />
        <span className="text-[13px] font-semibold text-slate-800">
          {r.estimated_loss_usd != null ? `$${Number(r.estimated_loss_usd).toLocaleString()}` : '—'}
        </span>
        <span className="text-[10px] text-slate-400">estimated loss</span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px]">
        <KV label="Product loss"     value={lb.product_loss_usd != null ? `$${Number(lb.product_loss_usd).toLocaleString()}` : null} />
        <KV label="Disposal"         value={lb.disposal_cost_usd != null ? `$${Number(lb.disposal_cost_usd).toLocaleString()}` : null} />
        <KV label="Disruption"       value={lb.downstream_disruption_usd != null ? `$${Number(lb.downstream_disruption_usd).toLocaleString()}` : null} />
        <KV label="Risk multiplier"  value={lb.risk_multiplier} mono />
        <KV label="Sub available"    value={r.substitute_available != null ? String(r.substitute_available) : null} />
        <KV label="Lead time"        value={r.replacement_lead_time_days != null ? `${r.replacement_lead_time_days}d (${r.expedited_lead_time_days}d exp.)` : null} />
      </div>
    </div>
  );
}

function NotificationResult({ r }) {
  return (
    <div className="space-y-1.5 text-[11px]">
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
        <KV label="Channel"    value={r.channel} />
        <KV label="Recipients" value={Array.isArray(r.recipients) ? r.recipients.join(', ') : r.recipients} />
        <KV label="Revised ETA" value={r.alert_payload?.revised_eta} mono />
        <KV label="Spoilage"   value={r.alert_payload?.spoilage_probability_pct != null ? `${r.alert_payload.spoilage_probability_pct}%` : null} />
        <KV label="Facility"   value={r.alert_payload?.facility_name} />
      </div>
      {r.message_preview && (
        <p className="text-[10px] text-slate-400 italic leading-snug">{r.message_preview}</p>
      )}
    </div>
  );
}

function ComplianceResult({ r }) {
  return (
    <div className="text-[11px] grid grid-cols-2 gap-x-4 gap-y-0.5">
      <KV label="Log ID"     value={r.log_id} mono />
      <KV label="Event"      value={r.event_type} />
      <KV label="Risk tier"  value={r.risk_tier} />
      <KV label="Regulatory" value={Array.isArray(r.regulatory_tags) ? r.regulatory_tags.join(', ') : null} />
    </div>
  );
}

function ApprovalResult({ r }) {
  return (
    <div className="text-[11px] grid grid-cols-2 gap-x-4 gap-y-0.5">
      <KV label="Approval ID" value={r.approval_id} mono />
      <KV label="Status"      value={r.status} />
      <KV label="Urgency"     value={r.urgency} />
    </div>
  );
}

function DefaultResult({ r }) {
  const keys = ['status', 'risk_tier', 'shipment_id', 'message'];
  return (
    <div className="text-[11px] grid grid-cols-2 gap-x-4 gap-y-0.5">
      {keys.filter(k => r[k]).map(k => <KV key={k} label={k} value={r[k]} />)}
    </div>
  );
}

function ToolResult({ tool, result: r }) {
  if (!r) return null;
  switch (tool) {
    case 'cold_storage_agent': return <ColdStorageResult r={r} />;
    case 'scheduling_agent':   return <SchedulingResult r={r} />;
    case 'insurance_agent':    return <InsuranceResult r={r} />;
    case 'notification_agent': return <NotificationResult r={r} />;
    case 'compliance_agent':   return <ComplianceResult r={r} />;
    case 'approval_workflow':  return <ApprovalResult r={r} />;
    default:                   return <DefaultResult r={r} />;
  }
}

// ── Main components ───────────────────────────────────────────────────

export default function AgentActivity() {
  const { data: history, loading, refetch } = useApi('/orchestrator/history?limit=30');
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

      <QuickRunPanel onRun={runSingle} running={running} />

      {loading && <p className="text-slate-500">Loading history...</p>}

      {history && history.length === 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-400">
          No orchestration decisions yet. Click the button above to run the agent on CRITICAL windows.
        </div>
      )}

      {history && history.map((dec, i) => (
        <DecisionCard key={i} decision={dec}
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

function DecisionCard({ decision, expanded, onToggle }) {
  const d = decision;
  const actionsCount = (d.actions_taken || []).length;

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
          <p className="text-sm text-slate-700">{d.decision_summary}</p>

          {d.draft_plan?.length > 0 && (
            <PlanSection title="Draft Plan" steps={d.draft_plan} />
          )}

          {d.reflection_notes?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Reflection Notes</p>
              {d.reflection_notes.map((n, j) => (
                <p key={j} className={`text-xs ${n.includes('GAP') ? 'text-amber-700' : 'text-green-700'}`}>{n}</p>
              ))}
            </div>
          )}

          {d.revised_plan?.length > 0 && (
            <PlanSection title="Revised Plan" steps={d.revised_plan} />
          )}

          {d.actions_taken?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Actions Taken</p>
              <div className="space-y-2">
                {d.actions_taken.map((a, j) => (
                  <div key={j} className="bg-slate-50 border border-slate-100 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold text-indigo-700 text-xs">{a.tool}</span>
                      {a.result?.status && (
                        <span className="text-[10px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded">
                          {a.result.status}
                        </span>
                      )}
                    </div>
                    <ToolResult tool={a.tool} result={a.result} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {d.fallback_plan?.length > 0 && (
            <PlanSection title="Fallback Plan" steps={d.fallback_plan} />
          )}

          {d.approval_id && (
            <p className="text-xs text-amber-700 font-medium">
              Approval ID: {d.approval_id} — {d.approval_reason}
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
