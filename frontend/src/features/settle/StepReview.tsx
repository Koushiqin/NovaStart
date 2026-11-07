import { useState } from "react"
import { apiClient } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

// P7 替换点：保持 {sessionId, onDone} 契约不变，只替换内部逻辑
interface StepProps {
  sessionId: number
  onDone: () => void
}

// 第④步占位：完成 = advance 到 4，后端同事务置 status=settled
export default function StepReview({ sessionId, onDone }: StepProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDone = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await apiClient.post(`/settle/${sessionId}/advance`, { to_step: 4 })
      onDone()
    } catch {
      setError("操作失败，请稍后重试")
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>第④步 · 回顾</CardTitle>
        <CardDescription>后续版本解锁：从过往里抽一段再读一遍。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button className="w-full" variant="outline" onClick={handleDone} disabled={busy}>
          {busy ? "处理中…" : "跳过"}
        </Button>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  )
}
