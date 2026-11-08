// 「连续 X 天 · 最长 Y 天」：数值全部来自 GET /api/progress/summary，前端不推算
export default function StreakBadge({ current, longest }: { current: number; longest: number }) {
  return (
    <p className="text-[13px] leading-relaxed text-[rgba(245,244,248,0.5)]">
      <span className="text-[15px] font-semibold tabular-nums text-[#f5f4f8]">{current}</span>
      <span className="ml-1.5">-day streak</span>
      <span className="mx-2 text-[rgba(245,244,248,0.3)]">·</span>
      <span>longest </span>
      <span className="tabular-nums text-[#f5f4f8]">{longest}</span>
    </p>
  )
}
