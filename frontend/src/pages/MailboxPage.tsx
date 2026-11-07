import { useCallback, useEffect, useState } from "react"
import axios from "axios"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import InboxList from "@/features/mailbox/InboxList"
import HistoryList from "@/features/mailbox/HistoryList"
import OutboxList from "@/features/mailbox/OutboxList"
import type {
  HistoryResponse,
  InboxResponse,
  Letter,
  OutboxLetter,
  OutboxResponse,
} from "@/features/mailbox/types"

// 信箱页：未处理 / 历史 / 发出记录三段；唯一写入路径是后端 letter 端点
export default function MailboxPage() {
  const userId = useAppStore((s) => s.userId)
  const [inbox, setInbox] = useState<Letter[]>([])
  const [history, setHistory] = useState<Letter[]>([])
  const [outbox, setOutbox] = useState<OutboxLetter[]>([])
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (userId == null) return
    // 账号快照：拉取中途切账号时丢弃过期响应，防止 A 的信件写入 B 的页面
    const accountId = userId
    try {
      const [inboxRes, historyRes, outboxRes] = await Promise.all([
        apiClient.get<InboxResponse>("/letters/inbox"),
        apiClient.get<HistoryResponse>("/letters/history"),
        apiClient.get<OutboxResponse>("/letters/outbox"),
      ])
      if (useAppStore.getState().userId !== accountId) return
      setInbox(inboxRes.data.letters)
      setHistory(historyRes.data.letters)
      setOutbox(outboxRes.data.letters)
    } catch {
      if (useAppStore.getState().userId !== accountId) return
      setError("信箱加载失败，请稍后重试")
    }
  }, [userId])

  useEffect(() => {
    setInbox([])
    setHistory([])
    setOutbox([])
    setError(null)
    void refresh()
  }, [refresh])

  // 过期信操作后端返回 409；统一刷新列表让该信从 inbox 消失
  const runLetterAction = async (letterId: number, run: () => Promise<unknown>) => {
    if (busyId !== null) return
    setBusyId(letterId)
    setError(null)
    try {
      await run()
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

  const handleFavorite = (id: number) =>
    runLetterAction(id, () => apiClient.post(`/letters/${id}/favorite`))
  const handleDismiss = (id: number) =>
    runLetterAction(id, () => apiClient.post(`/letters/${id}/dismiss`))
  const handleDelete = (id: number) =>
    runLetterAction(id, () => apiClient.delete(`/letters/${id}`))

  return (
    <div className="min-h-screen bg-background flex items-start justify-center p-6">
      <div className="w-full max-w-xl space-y-4">
        {userId == null ? (
          <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
            请先在右上角选择一个演示账号。
          </p>
        ) : (
          <>
            <Card>
              <CardHeader>
                <CardTitle>未处理</CardTitle>
              </CardHeader>
              <CardContent>
                <InboxList
                  letters={inbox}
                  busyId={busyId}
                  onFavorite={handleFavorite}
                  onDismiss={handleDismiss}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>历史信箱</CardTitle>
              </CardHeader>
              <CardContent>
                <HistoryList letters={history} busyId={busyId} onDelete={handleDelete} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>发出记录</CardTitle>
              </CardHeader>
              <CardContent>
                <OutboxList letters={outbox} />
              </CardContent>
            </Card>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </>
        )}
      </div>
    </div>
  )
}
