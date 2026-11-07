import { useState } from "react"
import { apiClient } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

// P6 替换点：保持 {sessionId, onDone} 契约不变，只替换内部逻辑
interface StepProps {
  sessionId: number
  onDone: () => void
}

// 第③步占位：跳过 = 推进到 settle_step 3
export default function StepMailbox({ sessionId, onDone }: StepProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSkip = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await apiClient.post(`/settle/${sessionId}/advance`, { to_step: 3 })
      onDone()
    } catch {
      setError("操作失败，请稍后重试")
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>第③步 · 信箱</CardTitle>
        <CardDescription>后续版本解锁：查看等待你的信。</CardDescription>
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
