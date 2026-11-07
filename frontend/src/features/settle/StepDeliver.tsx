import { useState } from "react"
import { apiClient } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

// P6 替换点：保持 {sessionId, onDone} 契约不变，只替换内部逻辑
interface StepProps {
  sessionId: number
  onDone: () => void
}

// 第②步占位：跳过 = 推进到 settle_step 2
export default function StepDeliver({ sessionId, onDone }: StepProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSkip = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await apiClient.post(`/settle/${sessionId}/advance`, { to_step: 2 })
      onDone()
    } catch {
      setError("操作失败，请稍后重试")
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>第②步 · 投递</CardTitle>
        <CardDescription>后续版本解锁：把这一场的心意投递出去。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button className="w-full" variant="outline" onClick={handleSkip} disabled={busy}>
          {busy ? "处理中…" : "跳过"}
        </Button>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  )
}
