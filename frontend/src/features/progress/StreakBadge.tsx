// 「连续 X 天 · 最长 Y 天」：数值全部来自 GET /api/progress/summary，前端不推算
export default function StreakBadge({ current, longest }: { current: number; longest: number }) {
  return (
    <div className="space-y-1 text-center">
      <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
        CURRENT STREAK
      </p>
      <div className="flex items-baseline justify-center gap-2">
        <span className="text-5xl font-semibold tabular-nums">{current}</span>
        <span className="text-sm">天连续</span>
        <span className="text-sm text-muted-foreground">· 最长 {longest} 天</span>
      </div>
    </div>
  )
}
