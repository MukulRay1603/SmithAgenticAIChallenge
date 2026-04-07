const COLORS = {
  CRITICAL: 'bg-red-100 text-red-800 ring-red-600/20',
  HIGH: 'bg-orange-100 text-orange-800 ring-orange-600/20',
  MEDIUM: 'bg-yellow-100 text-yellow-800 ring-yellow-600/20',
  LOW: 'bg-green-100 text-green-800 ring-green-600/20',
};

export default function TierBadge({ tier }) {
  const cls = COLORS[tier] || COLORS.LOW;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${cls}`}>
      {tier}
    </span>
  );
}
