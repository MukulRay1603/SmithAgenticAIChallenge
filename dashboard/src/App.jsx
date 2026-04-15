import { Routes, Route, NavLink } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getApi } from './hooks/useApi';
import {
  LayoutDashboard, Ship, ScrollText, CheckCircle, Activity,
  Bot, GitBranch, ShieldAlert, Brain, Wifi, WifiOff, ChevronRight,
} from 'lucide-react';
import Overview from './components/Overview';
import ShipmentList from './components/ShipmentList';
import ShipmentDetail from './components/ShipmentDetail';
import AuditLog from './components/AuditLog';
import Approvals from './components/Approvals';
import Monitoring from './components/Monitoring';
import AgentActivity from './components/AgentActivity';
import GraphView from './components/GraphView';

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/monitoring', icon: Activity, label: 'Monitoring' },
  { to: '/shipments', icon: Ship, label: 'Shipments' },
  { to: '/agent', icon: Bot, label: 'Agent Activity' },
  { to: '/graph', icon: GitBranch, label: 'System Graph' },
  { to: '/audit', icon: ScrollText, label: 'Audit Log' },
  { to: '/approvals', icon: CheckCircle, label: 'Approvals' },
];

function LLMBadge() {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    const load = () => getApi('/llm/status').then(setStatus).catch(() => {});
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  if (!status) return null;
  const active = status.active_provider;
  return (
    <div className="px-4 py-3 space-y-2">
      <div className="flex items-center gap-2">
        {active ? (
          <><Wifi className="w-3.5 h-3.5 text-emerald-400" /><span className="text-[11px] text-emerald-400 font-medium">LLM Online</span></>
        ) : (
          <><WifiOff className="w-3.5 h-3.5 text-slate-500" /><span className="text-[11px] text-slate-500">LLM Offline</span></>
        )}
      </div>
      {active && (
        <div className="flex items-center gap-1.5">
          <Brain className="w-3 h-3 text-violet-400" />
          <span className="text-[10px] text-violet-300 font-mono truncate">
            {status.active_model || active}
          </span>
        </div>
      )}
      <div className="text-[10px] text-slate-500">
        Mode: <span className="text-cyan-400 font-medium">{active ? 'Agentic' : 'Deterministic'}</span>
      </div>
    </div>
  );
}

function Sidebar() {
  return (
    <aside className="w-60 flex flex-col min-h-screen shrink-0 bg-[#0c1222] border-r border-white/[0.06]">
      <div className="px-5 py-5 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-violet-600 flex items-center justify-center">
            <ShieldAlert className="w-4.5 h-4.5 text-white" />
          </div>
          <div>
            <span className="text-sm font-bold tracking-tight text-white">AI Cargo</span>
            <p className="text-[10px] text-slate-500 leading-tight">Cold-Chain Intelligence</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-0.5">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to} to={to} end={to === '/'}
            className={({ isActive }) =>
              `group flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] transition-all duration-200
              ${isActive
                ? 'bg-gradient-to-r from-cyan-500/15 to-violet-500/10 text-cyan-300 font-medium shadow-sm shadow-cyan-500/5'
                : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'}`
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
            <ChevronRight className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-50 transition-opacity" />
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/[0.06]">
        <LLMBadge />
        <div className="px-4 pb-4 text-[10px] text-slate-600 space-y-0.5">
          <p>GDP / FDA 21 CFR 11 Compliant</p>
          <p>LangGraph + XGBoost + SHAP + RAG</p>
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <div className="flex min-h-screen bg-[#0f172a] text-slate-200">
      <Sidebar />
      <main className="flex-1 overflow-auto scrollbar-thin">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/shipments" element={<ShipmentList />} />
          <Route path="/shipments/:id" element={<ShipmentDetail />} />
          <Route path="/agent" element={<AgentActivity />} />
          <Route path="/graph" element={<GraphView />} />
          <Route path="/audit" element={<AuditLog />} />
          <Route path="/approvals" element={<Approvals />} />
        </Routes>
      </main>
    </div>
  );
}
