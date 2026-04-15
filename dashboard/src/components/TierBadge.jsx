const TIERS = {
  CRITICAL: {
    bg: 'bg-red-500/15',
    text: 'text-red-400',
    ring: 'ring-red-500/30',
    dot: 'bg-red-500',
  },
  HIGH: {
    bg: 'bg-orange-500/15',
    text: 'text-orange-400',
    ring: 'ring-orange-500/30',
    dot: 'bg-orange-500',
  },
  MEDIUM: {
    bg: 'bg-yellow-500/15',
    text: 'text-yellow-400',
    ring: 'ring-yellow-500/30',
    dot: 'bg-yellow-500',
  },
  LOW: {
    bg: 'bg-emerald-500/15',
    text: 'text-emerald-400',
    ring: 'ring-emerald-500/30',
    dot: 'bg-emerald-500',
  },
};

export default function TierBadge({ tier, size = 'sm' }) {
  const s = TIERS[tier] || TIERS.LOW;
  const sizeClasses = size === 'lg'
    ? 'px-3 py-1 text-xs'
    : 'px-2 py-0.5 text-[11px]';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ring-1 ring-inset ${s.bg} ${s.text} ${s.ring} ${sizeClasses}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${tier === 'CRITICAL' ? 'animate-pulse' : ''}`} />
      {tier}
    </span>
  );
}
