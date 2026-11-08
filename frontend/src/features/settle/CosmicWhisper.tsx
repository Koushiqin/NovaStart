import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import type { TodayResponse } from "@/features/task/types"

// 结算末态（A14 定稿文案）：四步走完才出现；「再学一场」按今日任务重新开一场
export default function CosmicWhisper() {
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId)
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRestart = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const today = await apiClient.get<TodayResponse>("/tasks/today")
      const task = today.data.task
      if (task === null) {
        // 跨零点无今日任务：回首页，由用户重新输入，不新建无主任务
        navigate("/")
        return
      }
      const created = await apiClient.post<{ session_id: number }>("/sessions", {
        task_id: task.id,
      })
      setCurrentSessionId(created.data.session_id)
      navigate("/focus")
    } catch {
      setError("操作失败，请稍后重试")
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardContent className="space-y-5 p-6 text-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
          SETTLED
        </p>
        <p className="text-xl font-semibold leading-relaxed">
          5 分钟的星星，
          <br />
          是你自己点亮的。
        </p>
        <div className="space-y-2">
          <Button className="w-full" onClick={handleRestart} disabled={busy}>
            {busy ? "进入中…" : "再学一场"}
          </Button>
          <Button className="w-full" variant="outline" onClick={() => navigate("/")} disabled={busy}>
            回到首页
          </Button>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  )
}
