import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import axios from "axios"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import TaskComposer from "@/features/task/TaskComposer"
import SplitEditor from "@/features/task/SplitEditor"
import type { AnalyzeResult, TaskResponse, TodayResponse } from "@/features/task/types"

interface CurrentSessionResponse {
  session: { id: number; ended_at: string | null } | null
}

// FastAPI 错误体可能是字符串或 {code, message}，422 时是校验错误数组
function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === "string") return detail
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message)
    }
    if (Array.isArray(detail)) return "输入不合法，请调整后重试"
    return error.message
  }
  return error instanceof Error ? error.message : String(error)
}

// 首页：今日任务入口（输入/标签 → 分析 → 编辑采用版 → 开始学习）
export default function HomePage() {
  const userId = useAppStore((s) => s.userId)
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId)
  const navigate = useNavigate()

  const [today, setToday] = useState<TodayResponse | null>(null)
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState<"analyze" | "save" | "start" | null>(null)
  const [error, setError] = useState<string | null>(null)

  // 切换账号即清空上一账号的任务、输入与在途状态，再按新身份拉取今日任务
  useEffect(() => {
    setToday(null)
    setInput("")
    setBusy(null)
    setError(null)
    if (userId == null) return

    let cancelled = false
    apiClient
      .get<TodayResponse>("/tasks/today")
      .then((res) => {
        if (cancelled) return
        setToday(res.data)
        setInput(res.data.task?.raw_text ?? "")
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e))
      })
    return () => {
      cancelled = true
    }
  }, [userId])

  const task = today?.task ?? null
  const locked = task?.locked ?? false

  // 请求返回时若账号已切换，丢弃结果，避免污染新账号视图
  const stillCurrentAccount = (accountId: number | null) =>
    useAppStore.getState().userId === accountId

  const handleAnalyze = async () => {
    const text = input.trim()
    if (!text || locked) return
    const accountId = userId
    setBusy("analyze")
    setError(null)
    try {
      let taskId = task?.id
      if (task === null) {
        const created = await apiClient.post<TaskResponse>("/tasks", { raw_text: text })
        taskId = created.data.task.id
      } else if (task.raw_text !== text) {
        const updated = await apiClient.patch<TaskResponse>(`/tasks/${task.id}`, {
          raw_text: text,
        })
        taskId = updated.data.task.id
      }
      await apiClient.post<AnalyzeResult>(`/tasks/${taskId}/analyze`)
      const refreshed = await apiClient.get<TodayResponse>("/tasks/today")
      if (!stillCurrentAccount(accountId)) return
      setToday(refreshed.data)
      setInput(refreshed.data.task?.raw_text ?? text)
    } catch (e) {
      if (stillCurrentAccount(accountId)) setError(errorMessage(e))
    } finally {
      if (stillCurrentAccount(accountId)) setBusy(null)
    }
  }

  const handleUpdate = (patch: { starter_step?: string; steps?: string[] }) => {
    if (!task || locked) return
    const accountId = userId
    const taskId = task.id
    setBusy("save")
    setError(null)
    apiClient
      .patch<TaskResponse>(`/tasks/${taskId}`, patch)
      .then((res) => {
        if (!stillCurrentAccount(accountId)) return
        setToday((prev) => (prev ? { ...prev, task: res.data.task } : prev))
      })
      .catch((e) => {
        if (stillCurrentAccount(accountId)) setError(errorMessage(e))
      })
      .finally(() => {
        if (stillCurrentAccount(accountId)) setBusy(null)
      })
  }

  const handleStart = async () => {
    if (!task || !task.analyzed) return
    const accountId = userId
    setBusy("start")
    setError(null)
    try {
      if (locked) {
        // 锁定态可能是进行中、已结束待结算，或已结算完成（无当前会话）
        const current = await apiClient.get<CurrentSessionResponse>("/sessions/current")
        if (!stillCurrentAccount(accountId)) return
        const ongoing = current.data.session
        if (ongoing && ongoing.ended_at === null) {
          navigate("/focus")
          return
        }
        if (ongoing && ongoing.ended_at !== null) {
          navigate("/settle")
          return
        }
      }
      const res = await apiClient.post<{ session_id: number }>("/sessions", { task_id: task.id })
      if (!stillCurrentAccount(accountId)) return
      setCurrentSessionId(res.data.session_id)
      navigate("/focus")
    } catch (e) {
      if (stillCurrentAccount(accountId)) setError(errorMessage(e))
    } finally {
      if (stillCurrentAccount(accountId)) setBusy(null)
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-start justify-center p-6">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>今日任务</CardTitle>
          <CardDescription>输入一句话，点「分析」得到五分钟的起步动作与后续路线。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {userId == null ? (
            <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
              请先在右上角选择一个演示账号。
            </p>
          ) : (
            <>
              <TaskComposer
                value={input}
                onChange={setInput}
                onAnalyze={handleAnalyze}
                analyzing={busy === "analyze"}
                disabled={locked || busy === "analyze"}
                carryOver={today?.carry_over ?? null}
                onContinueYesterday={() => setInput(today?.carry_over?.raw_text ?? "")}
              />

              {task?.analyzed && (
                <SplitEditor
                  task={task}
                  saving={busy === "save"}
                  titleChanged={input.trim().length > 0 && input.trim() !== task.raw_text}
                  onUpdate={handleUpdate}
                />
              )}

              <Button
                className="w-full"
                onClick={handleStart}
                disabled={!task?.analyzed || busy !== null}
              >
                {busy === "start" ? "进入中…" : locked ? "继续" : "开始学习"}
              </Button>
            </>
          )}

          {error && <p className="text-sm text-destructive">请求失败：{error}</p>}
        </CardContent>
      </Card>
    </div>
  )
}
