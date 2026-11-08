import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { apiClient } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

// P4 固定的组件契约，不得改签名
interface StepProps {
  sessionId: number
  onDone: () => void
}

interface ReviewItem {
  session_id: number
  date: string
  task_text: string
  reflection: string | null
}

interface RandomReviewResponse {
  item: ReviewItem | null
  server_time: string
}

// 第④步 · 回顾：mount 拉取一次过去的一条记录；池空只显示「等待宇宙的讯息」；完成推进到 4
export default function StepReview({ sessionId, onDone }: StepProps) {
  const navigate = useNavigate()
  const [item, setItem] = useState<ReviewItem | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setItem(null)
    setLoadError(false)
    setLoaded(false)

    const fetchReview = async () => {
      try {
        const res = await apiClient.get<RandomReviewResponse>("/review/random", {
          params: { exclude_session_id: sessionId },
          timeout: 5000, // 保证「完成」最多等 5 秒，避免请求悬挂时卡住结算
        })
        if (cancelled) return
        setItem(res.data.item)
      } catch {
        if (cancelled) return
        setLoadError(true)
      } finally {
        if (!cancelled) setLoaded(true)
      }
    }

    void fetchReview()
    return () => {
      cancelled = true
    }
  }, [sessionId])

  const handleDone = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await apiClient.post(`/settle/${sessionId}/advance`, { to_step: 4 })
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
          STEP 04 · REVIEW
        </p>
        <CardTitle>第④步 · 回顾</CardTitle>
        {loaded && !loadError && item !== null && (
          <CardDescription>从过去的记录里抽一条，作为这次的收尾。</CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {!loaded ? (
          <p className="text-sm text-muted-foreground">正在载入…</p>
        ) : loadError ? (
          <p className="text-sm text-destructive">回顾加载失败，请稍后重试</p>
        ) : item === null ? (
          <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
            等待宇宙的讯息
          </p>
        ) : (
          <button
            type="button"
            onClick={() => navigate(`/records?date=${item.date}`)}
            className="w-full rounded-lg border p-4 text-left transition-colors hover:bg-muted/60"
          >
            <p className="text-xs text-muted-foreground">过去的你 · {item.date}</p>
            <p className="mt-2 text-sm font-medium">{item.task_text}</p>
            {item.reflection !== null && (
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
                {item.reflection}
              </p>
            )}
          </button>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button className="w-full" variant="outline" onClick={handleDone} disabled={busy || !loaded}>
          {busy ? "处理中…" : "完成"}
        </Button>
      </CardContent>
    </Card>
  )
}
