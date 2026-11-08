import { useCallback, useEffect, useState } from "react"
import axios from "axios"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
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

// 信箱面板：未处理 / 历史 / 发出记录三段；唯一写入路径是后端 letter 端点
// 由首页「Mailbox」弹窗挂载
export default function MailboxPanel() {
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
    // 账号快照：动作开始后若切了账号，错误文案不能写到新账号的页面
    const accountId = useAppStore.getState().userId
    if (accountId == null) return
    const sameAccount = () => useAppStore.getState().userId === accountId
    setBusyId(letterId)
    setError(null)
    try {
      await run()
      await refresh()
    } catch (e) {
      if (!sameAccount()) return
      const code = axios.isAxiosError(e)
        ? (e.response?.data as { detail?: { code?: string } } | undefined)?.detail?.code
        : undefined
      if (code === "LETTER_ALREADY_HANDLED") {
        setError("这封信已处理，不能再收藏")
        // 该信已在别处被处理：同步刷新，避免本页留下点不动的陈旧卡片
        await refresh()
      } else if (code === "LETTER_EXPIRED" || (axios.isAxiosError(e) && e.response?.status === 409)) {
        setError("这封信已经过了一天")
        await refresh()
      } else {
        setError("操作失败，请稍后重试")
      }
    } finally {
      // 只清本地忙碌态，不写任何账号数据：无条件清空，避免切账号后永久卡住按钮
      setBusyId(null)
    }
  }

  const handleFavorite = (id: number) =>
    runLetterAction(id, () => apiClient.post(`/letters/${id}/favorite`))
  const handleDismiss = (id: number) =>
    runLetterAction(id, () => apiClient.post(`/letters/${id}/dismiss`))
  const handleDelete = (id: number) =>
    runLetterAction(id, () => apiClient.delete(`/letters/${id}`))

  if (userId == null) {
    return (
      <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
        请先登录后再查看信箱。
      </p>
    )
  }

  return (
    <div className="space-y-8">
      <section className="space-y-3 border-t border-border/60 pt-8 first:border-t-0 first:pt-0">
        <div className="space-y-1">
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
            INBOX
          </p>
          <h2 className="text-lg font-semibold">未处理</h2>
        </div>
        <InboxList
          letters={inbox}
          busyId={busyId}
          onFavorite={handleFavorite}
          onDismiss={handleDismiss}
        />
      </section>
      <section className="space-y-3 border-t border-border/60 pt-8 first:border-t-0 first:pt-0">
        <div className="space-y-1">
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
            ARCHIVE
          </p>
          <h2 className="text-lg font-semibold">历史信箱</h2>
        </div>
        <HistoryList letters={history} busyId={busyId} onDelete={handleDelete} />
      </section>
      <section className="space-y-3 border-t border-border/60 pt-8 first:border-t-0 first:pt-0">
        <div className="space-y-1">
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
            OUTBOX
          </p>
          <h2 className="text-lg font-semibold">发出记录</h2>
        </div>
        <OutboxList letters={outbox} />
      </section>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
