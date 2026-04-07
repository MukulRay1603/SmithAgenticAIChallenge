import { useApi } from '../hooks/useApi';
import { Link } from 'react-router-dom';
import {
  PieChart, Pie, Cell, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';
import { AlertTriangle, Thermometer, Package, Activity } from 'lucide-react';
import TierBadge from './TierBadge';

const TIER_COLORS = { CRITICAL: '#dc2626', HIGH: '#ea580c', MEDIUM: '#ca8a04', LOW: '#16a34a' };
const TIER_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

function StatCard({ icon: Icon, label, value, accent }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center gap-4 shadow-sm">
      <div className={`rounded-lg p-2.5 ${accent}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
    </div>
  );
}

export default function Overview() {
  const { data, loading, error } = useApi('/risk/overview');

  if (loading) return <div className="p-8 text-slate-500">Loading overview...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  const pieData = TIER_ORDER
    .filter(t => data.tier_counts[t])
    .map(t => ({ name: t, value: data.tier_counts[t] }));

  const barData = (data.top_risky_shipments || []).slice(0, 8).map(s => ({
    shipment: s.shipment_id,
    score: s.max_fused_score,
    tier: s.latest_risk_tier,
  }));

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold">Risk Overview</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard icon={Package} label="Total Windows" value={data.total_windows.toLocaleString()} accent="bg-slate-700" />
        <StatCard icon={Activity} label="Shipments" value={data.total_shipments} accent="bg-blue-600" />
        <StatCard icon={AlertTriangle} label="Critical" value={data.tier_counts.CRITICAL || 0} accent="bg-red-600" />
        <StatCard icon={Thermometer} label="High" value={data.tier_counts.HIGH || 0} accent="bg-orange-500" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-6">
        {/* Pie chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-600 mb-3">Tier Distribution</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                innerRadius={55} outerRadius={95} paddingAngle={3}>
                {pieData.map(d => (
                  <Cell key={d.name} fill={TIER_COLORS[d.name]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => v.toLocaleString()} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 mt-2">
            {pieData.map(d => (
              <span key={d.name} className="flex items-center gap-1.5 text-xs text-slate-600">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: TIER_COLORS[d.name] }} />
                {d.name}: {d.value}
              </span>
            ))}
          </div>
        </div>

        {/* Bar chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-600 mb-3">Top Risky Shipments</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="shipment" tick={{ fontSize: 11 }} width={55} />
              <Tooltip formatter={(v) => v.toFixed(4)} />
              <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                {barData.map((d, i) => (
                  <Cell key={i} fill={TIER_COLORS[d.tier] || '#64748b'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top risky shipments table */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-600 mb-3">Shipment Risk Summary</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-slate-500 uppercase tracking-wider">
                <th className="pb-2 pr-4">Shipment</th>
                <th className="pb-2 pr-4">Containers</th>
                <th className="pb-2 pr-4">Products</th>
                <th className="pb-2 pr-4">Windows</th>
                <th className="pb-2 pr-4">Latest Tier</th>
                <th className="pb-2 pr-4">Max Score</th>
                <th className="pb-2 pr-4">% Critical</th>
              </tr>
            </thead>
            <tbody>
              {(data.top_risky_shipments || []).slice(0, 10).map(s => (
                <tr key={s.shipment_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 pr-4">
                    <Link to={`/shipments/${s.shipment_id}`} className="text-blue-600 hover:underline font-medium">
                      {s.shipment_id}
                    </Link>
                  </td>
                  <td className="py-2 pr-4 text-slate-600">{s.containers.join(', ')}</td>
                  <td className="py-2 pr-4 text-slate-600">{s.products.join(', ')}</td>
                  <td className="py-2 pr-4">{s.total_windows}</td>
                  <td className="py-2 pr-4"><TierBadge tier={s.latest_risk_tier} /></td>
                  <td className="py-2 pr-4 font-mono">{s.max_fused_score.toFixed(4)}</td>
                  <td className="py-2 pr-4">{s.pct_critical}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
