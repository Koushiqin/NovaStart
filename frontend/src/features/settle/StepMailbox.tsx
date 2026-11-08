import { useCallback, useEffect, useState } from "react"
import axios from "axios"
import { apiClient } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import InboxList from "@/features/mailbox/InboxList"
import type { InboxResponse, Letter } from "@/features/mailbox/types"

// P4 固定的组件契约，不得改签名
interface StepProps {
  sessionId: number
  onDone: () => void
}

// 第③步 · 信箱：逐封收藏 / 放弃；「下一步」推进到 3（允许剩余信自然失效）
export default function StepMailbox({ sessionId, onDone }: StepProps) {
  const [letters, setLetters] = useState<Letter[]>([])
  const [busyId, setBusyId] = useState<number | null>(null)
  const [advancing, setAdvancing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await apiClient.get<InboxResponse>("/letters/inbox")
      setLetters(res.data.letters)
    } catch {
      setError("信箱加载失败，请稍后重试")
    }
  }, [])

  useEffect(() => {
    setLetters([])
    setError(null)
    void refresh()
  }, [refresh])

  // 收藏/放弃后刷新列表；409 = 信已过期，刷新后自然消失
  const handleAction = async (letterId: number, action: "favorite" | "dismiss") => {
    if (busyId !== null) return
    setBusyId(letterId)
    setError(null)
    try {
      await apiClient.post(`/letters/${letterId}/${action}`)
      await refresh()
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.status === 409) {
        setError("这封信已经过了一天")
        await refresh()
      } else {
        setError("操作失败，请稍后重试")
      }
    } finally {
      setBusyId(null)
    }
  }

  const handleNext = async () => {
    if (advancing) return
    setAdvancing(true)
    setError(null)
    try {
      await apiClient.post(`/settle/${sessionId}/advance`, { to_step: 3 })
      // 步骤推进以 summary 刷新为准；刷新失败时恢复按钮，允许再次点击重试
      await Promise.resolve(onDone())
    } catch {
      setError("操作失败，请稍后重试")
    } finally {
      setAdvancing(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
          STEP 03 · MAILBOX
        </p>
        <CardTitle>第③步 · 信箱</CardTitle>
        <CardDescription>收藏想留下的信，其余的放弃。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <InboxList
          letters={letters}
          busyId={busyId}
          onFavorite={(id) => void handleAction(id, "favorite")}
          onDismiss={(id) => void handleAction(id, "dismiss")}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button className="w-full" variant="outline" onClick={handleNext} disabled={advancing}>
          {advancing ? "处理中…" : "下一步"}
        </Button>
      </CardContent>
    </Card>
  )
}
