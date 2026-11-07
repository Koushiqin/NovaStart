import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import axios from "axios"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
import SettleSummary, { type SettleSummaryData } from "@/features/settle/SettleSummary"
import StepReflection from "@/features/settle/StepReflection"
import StepDeliver from "@/features/settle/StepDeliver"
import StepMailbox from "@/features/settle/StepMailbox"
import StepReview from "@/features/settle/StepReview"
import CosmicWhisper from "@/features/settle/CosmicWhisper"

interface CurrentSessionResponse {
  session: { id: number; status: string; ended_at: string | null } | null
}

// 结算页：断点只读服务端 settle_step（summary 是唯一来源），不在前端另存进度。
// 会话解析：已结束的 current 会话优先；第④步完成（settled）后 /current 不再返回，
// 当次页面用内存中的 currentSessionId 拉 summary；两者都无则回首页。
export default function SettlePage() {
  const userId = useAppStore((s) => s.userId)
  const navigate = useNavigate()
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [summary, setSummary] = useState<SettleSummaryData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (userId == null) {
      setSessionId(null)
      setSummary(null)
      setError(null)
      return
    }

    const accountId = userId
    let cancelled = false
    setSessionId(null)
    setSummary(null)
    setError(null)
    setLoading(true)

    const resolve = async () => {
      try {
        const current = await apiClient.get<CurrentSessionResponse>("/sessions/current")
        if (cancelled || useAppStore.getState().userId !== accountId) return

        const currentSession = current.data.session
        const id =
          currentSession !== null && currentSession.ended_at !== null
            ? currentSession.id
            : useAppStore.getState().currentSessionId
        if (id == null) {
          navigate("/")
          return
        }
        setSessionId(id)

        const res = await apiClient.get<SettleSummaryData>(`/sessions/${id}/summary`)
        if (cancelled || useAppStore.getState().userId !== accountId) return
        setSummary(res.data)
      } catch (e) {
        if (cancelled || useAppStore.getState().userId !== accountId) return
        if (axios.isAxiosError(e) && e.response?.status === 404) {
          navigate("/")
          return
        }
        setError("结算信息加载失败，请稍后重试")
      } finally {
        if (!cancelled && useAppStore.getState().userId === accountId) setLoading(false)
      }
    }

    void resolve()
    return () => {
      cancelled = true
    }
  }, [userId, navigate])

  // 每一步完成后重新拉 summary：断点由服务端返回，前端只做显示器
  const handleDone = async () => {
    if (sessionId == null) return
    const accountId = userId
    try {
      const res = await apiClient.get<SettleSummaryData>(`/sessions/${sessionId}/summary`)
      if (useAppStore.getState().userId !== accountId) return
      setSummary(res.data)
      setError(null)
    } catch (e) {
      if (useAppStore.getState().userId !== accountId) return
      if (axios.isAxiosError(e) && e.response?.status === 404) {
        navigate("/")
        return
      }
      setError("结算信息加载失败，请稍后重试")
    }
  }

  const renderStep = () => {
    if (sessionId === null || summary === null) return null
    switch (summary.settle_step) {
      case 0:
        return <StepReflection sessionId={sessionId} onDone={handleDone} />
      case 1:
        return <StepDeliver sessionId={sessionId} onDone={handleDone} />
      case 2:
        return <StepMailbox sessionId={sessionId} onDone={handleDone} />
      default:
        return <StepReview sessionId={sessionId} onDone={handleDone} />
    }
  }

  return (
    <div className="flex min-h-screen items-start justify-center bg-background p-6">
      <div className="w-full max-w-md space-y-6">
        {userId == null ? (
          <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
            请先在右上角选择一个演示账号。
          </p>
        ) : summary !== null && sessionId !== null ? (
          <>
            <SettleSummary data={summary} />
            {summary.settle_step >= 4 ? <CosmicWhisper /> : renderStep()}
            {summary !== null && error !== null && (
              <p className="text-center text-sm text-destructive">{error}</p>
            )}
          </>
        ) : error !== null ? (
          <p className="text-center text-sm text-destructive">{error}</p>
        ) : (
          <p className="text-center text-sm text-muted-foreground">
            {loading ? "正在载入…" : "正在返回首页…"}
          </p>
        )}
      </div>
    </div>
  )
}
