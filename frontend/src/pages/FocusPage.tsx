import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import axios from "axios"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
import { useServerClock } from "@/hooks/useServerClock"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import FocusTimer from "@/features/focus/FocusTimer"
import MilestoneBanner from "@/features/focus/MilestoneBanner"

// 与 backend/app/schemas/session.py 的 SessionInfo 对应（专注页唯一消费者，类型就近维护）
interface SessionInfo {
  id: number
  started_at: string
  elapsed_sec: number
  status: string
  ended_at: string | null
  task_starter_step: string | null
}

interface CurrentSessionResponse {
  session: SessionInfo | null
  server_time: string
}

interface SessionEndedResponse {
  result: "settled" | "discarded"
  duration_sec: number | null
  short_by_sec: number | null
  server_time: string
}

// 轮询间隔：每 15 秒由服务端懒标记校正状态，并刷新 server_time 偏移
const POLL_INTERVAL_MS = 15_000
// 无效结束的差额提示停留时间
const DISCARD_NOTICE_MS = 2_000

// FastAPI 错误体可能是字符串或 {code, message}，422 时是校验错误数组
function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === "string") return detail
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message)
    }
    if (Array.isArray(detail)) return "请求不合法，请稍后重试"
    return error.message
  }
  return error instanceof Error ? error.message : String(error)
}

function formatShortBy(shortBySec: number): string {
  const minutes = Math.floor(shortBySec / 60)
  const seconds = shortBySec % 60
  return `还差 ${minutes} 分 ${seconds} 秒`
}

// 专注页：以 GET /sessions/current 为权威续算正计时，轮询触发服务端懒标记，
// 结束唯一入口是 POST /sessions/{id}/end（有效进结算、无效提示差额后回首页）。
export default function FocusPage() {
  const userId = useAppStore((s) => s.userId)
  const navigate = useNavigate()
  const clock = useServerClock()

  const [session, setSession] = useState<SessionInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ending, setEnding] = useState(false)
  const [discardNotice, setDiscardNotice] = useState<string | null>(null)
  // 仅用于每秒重渲染，派生时间始终来自服务端 started_at + useServerClock
  const [, forceTick] = useState(0)
  // 已发起离开（跳结算/回首页）后停止轮询写入，避免重复导航
  const leavingRef = useRef(false)

  // 挂载/切账号：拉取当前会话；无会话回首页；账号未选不发业务请求
  useEffect(() => {
    setSession(null)
    setError(null)
    setDiscardNotice(null)
    setEnding(false)
    leavingRef.current = false
    if (userId == null) return

    let cancelled = false
    setLoading(true)
    apiClient
      .get<CurrentSessionResponse>("/sessions/current")
      .then((res) => {
        if (cancelled) return
        const current = res.data.session
        if (current === null) {
          leavingRef.current = true
          navigate("/")
          return
        }
        setSession(current)
        // 180 分钟封顶或他处已结束：直接去结算，不再停留计时
        if (current.ended_at !== null) {
          leavingRef.current = true
          navigate("/settle")
        }
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [userId, navigate])

  // 1 秒重渲染，让「服务端当前时间 − started_at」持续递增
  useEffect(() => {
    const id = window.setInterval(() => forceTick((value) => value + 1), 1_000)
    return () => window.clearInterval(id)
  }, [])

  // 15 秒轮询：触发 5 分钟/180 分钟懒标记，并用响应里的 server_time 校正偏移
  useEffect(() => {
    if (userId == null) return
    const id = window.setInterval(() => {
      if (leavingRef.current) return
      apiClient
        .get<CurrentSessionResponse>("/sessions/current")
        .then((res) => {
          if (leavingRef.current) return
          const current = res.data.session
          if (current === null) return
          setSession(current)
          if (current.ended_at !== null) {
            leavingRef.current = true
            navigate("/settle")
          }
        })
        .catch(() => {
          // 单次轮询失败不打断本地计时，下次轮询继续用服务端数据校正
        })
    }, POLL_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [userId, navigate])

  const handleEnd = async () => {
    if (!session || ending) return
    setEnding(true)
    setError(null)
    try {
      const res = await apiClient.post<SessionEndedResponse>(`/sessions/${session.id}/end`)
      if (res.data.result === "settled") {
        leavingRef.current = true
        navigate("/settle")
        return
      }
      setDiscardNotice(formatShortBy(res.data.short_by_sec ?? 0))
      window.setTimeout(() => {
        leavingRef.current = true
        navigate("/")
      }, DISCARD_NOTICE_MS)
    } catch (e) {
      setError(errorMessage(e))
      setEnding(false)
    }
  }

  if (userId == null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <p className="text-sm text-muted-foreground">请先在右上角选择一个演示账号。</p>
      </div>
    )
  }

  const startedAtMs = session === null ? null : Date.parse(session.started_at)
  const elapsedSec =
    startedAtMs !== null && !Number.isNaN(startedAtMs)
      ? Math.max(0, Math.floor((clock.now().getTime() - startedAtMs) / 1000))
      : session?.elapsed_sec ?? 0
  // 已满最短时长但未结束：展示一次性里程碑提示，背景略亮，计时继续
  const milestone = session !== null && session.status === "completed" && session.ended_at === null

  return (
    <div
      className={cn(
        "flex min-h-screen items-center justify-center p-6 transition-colors duration-700",
        milestone ? "bg-secondary/40" : "bg-background"
      )}
    >
      <div className="w-full max-w-md space-y-8">
        {session ? (
          <>
            <div className="space-y-2 text-center">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">本次专注</p>
              <p className="text-base font-medium">
                {session.task_starter_step ?? "今天的任务"}
              </p>
            </div>

            <FocusTimer elapsedSec={elapsedSec} />

            {milestone && <MilestoneBanner />}

            <div className="space-y-3">
              <Button
                className="w-full"
                size="lg"
                variant={milestone ? "default" : "outline"}
                onClick={handleEnd}
                disabled={ending}
              >
                {ending ? "结束中…" : "结束"}
              </Button>
              {discardNotice && (
                <p className="text-center text-sm text-muted-foreground">{discardNotice}</p>
              )}
              {error && <p className="text-center text-sm text-destructive">请求失败：{error}</p>}
            </div>
          </>
        ) : (
          <p className="text-center text-sm text-muted-foreground">
            {loading ? "正在载入…" : error ?? "正在返回首页…"}
          </p>
        )}
      </div>
    </div>
  )
}
