import { useApi } from '../hooks/useApi';
import { Link } from 'react-router-dom';
import {
  PieChart, Pie, Cell, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';
import { AlertTriangle, Thermometer, Package, Activity, TrendingUp, ShieldCheck } from 'lucide-react';
import TierBadge from './TierBadge';

const TIER_COLORS = { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#22c55e' };
const TIER_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

const STAT_CONFIGS = [
  { key: 'windows', icon: Package, label: 'Total Windows', gradient: 'from-cyan-500 to-blue-600', bgGlow: 'shadow-cyan-500/10' },
  { key: 'shipments', icon: Activity, label: 'Active Shipments', gradient: 'from-violet-500 to-purple-600', bgGlow: 'shadow-violet-500/10' },
  { key: 'critical', icon: AlertTriangle, label: 'Critical Alerts', gradient: 'from-red-500 to-rose-600', bgGlow: 'shadow-red-500/10' },
  { key: 'high', icon: Thermometer, label: 'High Risk', gradient: 'from-orange-500 to-amber-600', bgGlow: 'shadow-orange-500/10' },
];

function StatCard({ icon: Icon, label, value, gradient, bgGlow, delay }) {
  return (
    <div className={`glass-card p-5 animate-slide-up shadow-lg ${bgGlow}`} style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] text-slate-400 uppercase tracking-wider font-medium">{label}</p>
          <p className="text-3xl font-bold mt-1.5 text-white tabular-nums">{value}</p>
        </div>
        <div className={`rounded-xl p-2.5 bg-gradient-to-br ${gradient}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="glass-card-sm px-3 py-2 text-xs">
      <p className="font-semibold text-white">{d.shipment || d.name}</p>
      <p className="text-slate-400 mt-0.5">
        {d.score != null ? `Score: ${d.score.toFixed(4)}` : `Count: ${d.value}`}
      </p>
    </div>
  );
}

export default function Overview() {
  const { data, loading, error } = useApi('/risk/overview');

  if (loading) return (
    <div className="p-8 flex items-center gap-3 text-slate-500">
      <div className="w-5 h-5 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
      Loading risk overview...
    </div>
  );
  if (error) return <div className="p-8 text-red-400">Error: {error}</div>;

  const pieData = TIER_ORDER.filter(t => data.tier_counts[t]).map(t => ({ name: t, value: data.tier_counts[t] }));
  const totalWindows = pieData.reduce((s, d) => s + d.value, 0);
  const barData = (data.top_risky_shipments || []).slice(0, 8).map(s => ({
    shipment: s.shipment_id,
    score: s.max_fused_score,
    tier: s.latest_risk_tier,
  }));
  const statValues = {
    windows: data.total_windows.toLocaleString(),
    shipments: data.total_shipments,
    critical: data.tier_counts.CRITICAL || 0,
    high: data.tier_counts.HIGH || 0,
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Risk Overview</h1>
          <p className="text-sm text-slate-500 mt-0.5">Pharmaceutical cold-chain monitoring dashboard</p>
        </div>
        <div className="flex items-center gap-2 glass-card-sm px-3 py-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-xs text-emerald-400 font-medium">GDP Compliant</span>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {STAT_CONFIGS.map((cfg, i) => {
          const { key, ...rest } = cfg;
          return <StatCard key={key} {...rest} value={statValues[key]} delay={i * 80} />;
        })}
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="glass-card p-6 animate-slide-up" style={{ animationDelay: '320ms' }}>
          <h2 className="text-sm font-semibold text-slate-300 mb-1">Tier Distribution</h2>
          <p className="text-[11px] text-slate-500 mb-4">Risk classification breakdown across all windows</p>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                innerRadius={65} outerRadius={100} paddingAngle={3} strokeWidth={0}>
                {pieData.map(d => (
                  <Cell key={d.name} fill={TIER_COLORS[d.name]} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <text x="50%" y="46%" textAnchor="middle" className="fill-white text-2xl font-bold">{totalWindows}</text>
              <text x="50%" y="56%" textAnchor="middle" className="fill-slate-400 text-[11px]">total</text>
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-5 mt-3">
            {pieData.map(d => (
              <span key={d.name} className="flex items-center gap-1.5 text-xs text-slate-400">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: TIER_COLORS[d.name] }} />
                {d.name} <span className="text-slate-500 font-mono">{d.value}</span>
              </span>
            ))}
          </div>
        </div>

        <div className="glass-card p-6 animate-slide-up" style={{ animationDelay: '400ms' }}>
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-semibold text-slate-300">Top Risky Shipments</h2>
            <TrendingUp className="w-4 h-4 text-slate-500" />
          </div>
          <p className="text-[11px] text-slate-500 mb-4">Highest fused risk scores across active shipments</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 10, fill: '#64748b' }} stroke="transparent" />
              <YAxis type="category" dataKey="shipment" tick={{ fontSize: 10, fill: '#94a3b8' }} width={60} stroke="transparent" />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="score" radius={[0, 6, 6, 0]}>
                {barData.map((d, i) => (
                  <Cell key={i} fill={TIER_COLORS[d.tier] || '#64748b'} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="glass-card p-6 animate-slide-up" style={{ animationDelay: '480ms' }}>
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Shipment Risk Summary</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06] text-left text-[11px] text-slate-500 uppercase tracking-wider">
                <th className="pb-3 pr-4 font-medium">Shipment</th>
                <th className="pb-3 pr-4 font-medium">Containers</th>
                <th className="pb-3 pr-4 font-medium">Products</th>
                <th className="pb-3 pr-4 font-medium">Windows</th>
                <th className="pb-3 pr-4 font-medium">Latest Tier</th>
                <th className="pb-3 pr-4 font-medium">Max Score</th>
                <th className="pb-3 pr-4 font-medium">% Critical</th>
              </tr>
            </thead>
            <tbody>
              {(data.top_risky_shipments || []).slice(0, 10).map((s, i) => (
                <tr key={s.shipment_id}
                    className="border-b border-white/[0.04] hover:bg-white/[0.02] transition animate-fade-in"
                    style={{ animationDelay: `${560 + i * 40}ms` }}>
                  <td className="py-3 pr-4">
                    <Link to={`/shipments/${s.shipment_id}`} className="text-cyan-400 hover:text-cyan-300 font-medium transition">
                      {s.shipment_id}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-slate-400">{s.containers.join(', ')}</td>
                  <td className="py-3 pr-4 text-slate-400">{s.products.join(', ')}</td>
                  <td className="py-3 pr-4 text-slate-300">{s.total_windows}</td>
                  <td className="py-3 pr-4"><TierBadge tier={s.latest_risk_tier} /></td>
                  <td className="py-3 pr-4 font-mono text-white">{s.max_fused_score.toFixed(4)}</td>
                  <td className="py-3 pr-4">
                    <span className={`font-mono ${s.pct_critical > 30 ? 'text-red-400' : 'text-slate-400'}`}>
                      {s.pct_critical}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
