// 正计时纯展示：数值由页面从服务端 started_at 派生，本组件只负责 mm:ss 渲染
interface FocusTimerProps {
  elapsedSec: number
}

function formatElapsed(totalSec: number): string {
  const minutes = Math.floor(totalSec / 60)
  const seconds = totalSec % 60
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
}

export default function FocusTimer({ elapsedSec }: FocusTimerProps) {
  return (
    <div className="space-y-2 text-center">
      <p
        className="font-mono font-semibold tabular-nums tracking-tight"
        style={{ fontSize: "clamp(3.5rem, 12vw, 5rem)", lineHeight: 1 }}
      >
        {formatElapsed(Math.max(0, elapsedSec))}
      </p>
      <p className="text-xs text-muted-foreground">从开始就不再停下，先做五分钟。</p>
    </div>
  )
}
