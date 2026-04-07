import { Routes, Route, NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Ship,
  ScrollText,
  CheckCircle,
  Activity,
  Bot,
  GitBranch,
  ShieldAlert,
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

function Sidebar() {
  return (
    <aside className="w-56 bg-slate-900 text-slate-200 flex flex-col min-h-screen shrink-0">
      <div className="px-5 py-5 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-6 h-6 text-amber-400" />
          <span className="text-base font-bold tracking-tight">AI Cargo Monitor</span>
        </div>
        <p className="text-[11px] text-slate-400 mt-1">Cold-Chain Risk Intelligence</p>
      </div>
      <nav className="flex-1 py-4 space-y-0.5 px-3">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition
              ${isActive ? 'bg-slate-700 text-white font-medium' : 'text-slate-400 hover:bg-slate-800 hover:text-white'}`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-3 text-[10px] text-slate-500 border-t border-slate-700 space-y-0.5">
        <p>GDP / FDA 21 CFR 11 Compliant</p>
        <p>LangGraph + XGBoost + SHAP</p>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-800">
      <Sidebar />
      <main className="flex-1 overflow-auto">
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
