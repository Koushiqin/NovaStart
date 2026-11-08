import { useState } from "react"
import axios from "axios"
import { apiClient } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { LetterSendResult, SendResult } from "@/features/mailbox/types"

// P4 固定的组件契约，不得改签名
interface StepProps {
  sessionId: number
  onDone: () => void
}

const RESULT_TEXT: Record<SendResult, string> = {
  delivered: "已投递",
  rejected_full: "对方信箱已满，可改寄",
  rejected_unknown: "找不到这位同学",
  already_sent: "已寄出",
}

// 第②步 · 投递：本场可投 1 封；拒收/找不到不消耗机会，可改寄；「不寄了」= 跳过推进
export default function StepDeliver({ sessionId, onDone }: StepProps) {
  const [recipient, setRecipient] = useState("")
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<SendResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // 投递成功或本场已寄出后，本步只剩「下一步」
  const finished = result === "delivered" || result === "already_sent"

  const handleSend = async () => {
    if (busy || finished) return
    const name = recipient.trim()
    if (!name) return
    setBusy(true)
    setError(null)
    try {
      const res = await apiClient.post<LetterSendResult>("/letters", {
        session_id: sessionId,
        recipient_name: name,
      })
      setResult(res.data.result)
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.status === 409) {
        setError("这场学习还不能投递")
      } else if (axios.isAxiosError(e) && e.response?.status === 422) {
        setError("收件人不能为空")
      } else {
        setError("操作失败，请稍后重试")
      }
    } finally {
      setBusy(false)
    }
  }

  const handleNext = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await apiClient.post(`/settle/${sessionId}/advance`, { to_step: 2 })
      // 步骤推进以 summary 刷新为准；刷新失败时恢复按钮，允许再次点击重试
      await Promise.resolve(onDone())
    } catch {
      setError("操作失败，请稍后重试")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
          STEP 02 · DELIVER
        </p>
        <CardTitle>第②步 · 投递</CardTitle>
        <CardDescription>本场可投 1 封，把这一场的心意寄给一位同学。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {!finished && (
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
              placeholder="收件人昵称或 ID"
              value={recipient}
              maxLength={50}
              onChange={(e) => setRecipient(e.target.value)}
              disabled={busy}
            />
            <Button onClick={handleSend} disabled={busy || !recipient.trim()}>
              {busy ? "寄出中…" : "寄出"}
            </Button>
          </div>
        )}

        {result !== null && (
          <p
            className={
              result === "delivered" ? "text-sm" : "text-sm text-muted-foreground"
            }
          >
            {RESULT_TEXT[result]}
          </p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}

        <Button className="w-full" variant="outline" onClick={handleNext} disabled={busy}>
          {finished ? "下一步" : "不寄了"}
        </Button>
      </CardContent>
    </Card>
  )
}
