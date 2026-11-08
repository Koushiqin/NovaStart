import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import axios from "axios"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import Modal from "@/components/ui/modal"
import TaskComposer from "@/features/task/TaskComposer"
import SplitEditor from "@/features/task/SplitEditor"
import type { AnalyzeResult, TaskResponse, TodayResponse } from "@/features/task/types"
import StarWall, { type ProgressSummaryData } from "@/features/progress/StarWall"
import StreakBadge from "@/features/progress/StreakBadge"

interface CurrentSessionResponse {
  session: { id: number; ended_at: string | null } | null
}

interface LetterItem {
  id: number
  content: string
  sender_name: string | null
  created_at: string
}

interface SessionRecord {
  session_id: number
  started_at: string
  ended_at: string | null
  task_title: string
  reflection: string | null
}

interface ReviewItem {
  session_id: number
  date: string
  task_text: string
  reflection: string | null
}

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

// 首页：Hero + 开始学习弹窗 + 连续天数/星星墙 + 三个历史功能弹窗
export default function HomePage() {
  const userId = useAppStore((s) => s.userId)
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId)
  const navigate = useNavigate()

  const [progress, setProgress] = useState<ProgressSummaryData | null>(null)
  const [today, setToday] = useState<TodayResponse | null>(null)
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState<"analyze" | "save" | "start" | null>(null)
  const [error, setError] = useState<string | null>(null)

  // 弹窗状态
  const [startOpen, setStartOpen] = useState(false)
  const [lettersOpen, setLettersOpen] = useState(false)
  const [recordsOpen, setRecordsOpen] = useState(false)
  const [reflectionOpen, setReflectionOpen] = useState(false)

  // 历史信件
  const [letters, setLetters] = useState<LetterItem[]>([])
  const [lettersLoading, setLettersLoading] = useState(false)

  // 历史记录：年/月/日下拉
  const [recYear, setRecYear] = useState<number>(new Date().getFullYear())
  const [recMonth, setRecMonth] = useState<number>(new Date().getMonth() + 1)
  const [recDay, setRecDay] = useState<number>(new Date().getDate())
  const [records, setRecords] = useState<SessionRecord[] | null>(null)
  const [recordsError, setRecordsError] = useState<string | null>(null)

  // 随机感想
  const [review, setReview] = useState<ReviewItem | null>(null)

  // 拉取进度
  useEffect(() => {
    setProgress(null)
    if (userId == null) return
    apiClient
      .get<ProgressSummaryData>("/progress/summary")
      .then((res) => setProgress(res.data))
      .catch(() => setProgress(null))
  }, [userId])

  // 打开开始学习弹窗时拉取今日任务
  useEffect(() => {
    if (!startOpen || userId == null) return
    setToday(null)
    setInput("")
    setBusy(null)
    setError(null)
    apiClient
      .get<TodayResponse>("/tasks/today")
      .then((res) => {
        setToday(res.data)
        setInput(res.data.task?.raw_text ?? "")
      })
      .catch((e) => setError(errorMessage(e)))
  }, [startOpen, userId])

  const stillCurrentAccount = (accountId: number | null) =>
    useAppStore.getState().userId === accountId

  const handleAnalyze = async () => {
    const text = input.trim()
    const task = today?.task ?? null
    if (!text || task?.locked) return
    const accountId = userId
    setBusy("analyze")
    setError(null)
    try {
      let taskId = task?.id
      if (task === null) {
        const created = await apiClient.post<TaskResponse>("/tasks", { raw_text: text })
        taskId = created.data.task.id
      } else if (task.raw_text !== text) {
        const updated = await apiClient.patch<TaskResponse>(`/tasks/${task.id}`, { raw_text: text })
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
    const task = today?.task ?? null
    if (!task || task.locked) return
    const accountId = userId
    setBusy("save")
    setError(null)
    apiClient
      .patch<TaskResponse>(`/tasks/${task.id}`, patch)
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
    const task = today?.task ?? null
    if (!task || !task.analyzed) return
    const accountId = userId
    setBusy("start")
    setError(null)
    try {
      if (task.locked) {
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
      setStartOpen(false)
      navigate("/focus")
    } catch (e) {
      if (stillCurrentAccount(accountId)) setError(errorMessage(e))
    } finally {
      if (stillCurrentAccount(accountId)) setBusy(null)
    }
  }

  const loadLetters = async () => {
    setLettersLoading(true)
    try {
      const res = await apiClient.get<{ letters: LetterItem[] }>("/letters/history")
      setLetters(res.data.letters)
    } catch {
      setLetters([])
    } finally {
      setLettersLoading(false)
    }
  }

  const queryRecords = async () => {
    const dateStr = `${recYear}-${String(recMonth).padStart(2, "0")}-${String(recDay).padStart(2, "0")}`
    setRecordsError(null)
    setRecords(null)
    try {
      const res = await apiClient.get<{ items: SessionRecord[] }>("/sessions/by-date", {
        params: { date: dateStr },
      })
      setRecords(res.data.items)
    } catch (e) {
      setRecordsError(errorMessage(e))
    }
  }

  const loadReview = async () => {
    try {
      const res = await apiClient.get<{ item: ReviewItem | null }>("/review/daily")
      setReview(res.data.item)
    } catch {
      setReview(null)
    }
  }

  const task = today?.task ?? null
  const locked = task?.locked ?? false

  const years = Array.from({ length: 10 }, (_, i) => new Date().getFullYear() - 5 + i)
  const daysInMonth = new Date(recYear, recMonth, 0).getDate()

  return (
    <div className="min-h-screen bg-background">
      {/* Hero */}
      <section className="border-b bg-gradient-to-b from-primary/5 to-transparent">
        <div className="mx-auto max-w-3xl px-6 py-12 text-center">
          <h1 className="text-4xl font-bold tracking-tight">NovaStart</h1>
          <p className="mt-2 text-lg text-muted-foreground">每天五分钟，主动学习一点点</p>
          {/* 图片占位 */}
          <div className="mx-auto mt-6 aspect-video w-full max-w-2xl rounded-xl border border-dashed bg-muted/40 flex items-center justify-center text-muted-foreground">
            图片占位
          </div>
          <div className="mt-6">
            <Button
              size="lg"
              disabled={userId == null}
              onClick={() => setStartOpen(true)}
            >
              开始今日的五分钟学习
            </Button>
            <p className="mt-2 text-sm text-muted-foreground">
              开始学习以获得别人的信件
            </p>
          </div>
        </div>
      </section>

      {/* 已登录功能区 */}
      {userId != null && (
        <div className="mx-auto max-w-3xl space-y-4 px-6 py-8">
          {progress !== null && (
            <Card>
              <CardContent className="space-y-4 p-5">
                <StreakBadge current={progress.streak.current} longest={progress.streak.longest} />
                <StarWall wall={progress.wall} />
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Button variant="outline" onClick={() => { setLettersOpen(true); void loadLetters() }}>
              历史收藏信件
            </Button>
            <Button variant="outline" onClick={() => { setRecordsOpen(true); setRecords(null); setRecordsError(null) }}>
              历史学习记录
            </Button>
            <Button variant="outline" onClick={() => { setReflectionOpen(true); void loadReview() }}>
              随机回顾感想
            </Button>
          </div>
        </div>
      )}

      {/* 开始学习弹窗 */}
      <Modal open={startOpen} onClose={() => setStartOpen(false)} title="开始今日的五分钟学习">
        <div className="space-y-4">
          {userId == null ? (
            <p className="text-center text-sm text-muted-foreground">请先登录</p>
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
        </div>
      </Modal>

      {/* 历史收藏信件弹窗 */}
      <Modal open={lettersOpen} onClose={() => setLettersOpen(false)} title="历史收藏信件">
        {lettersLoading ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : letters.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无收藏信件</p>
        ) : (
          <ul className="max-h-[60vh] space-y-3 overflow-y-auto">
            {letters.map((l) => (
              <li key={l.id} className="rounded-md border p-3">
                <p className="text-sm">{l.content}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {l.sender_name ?? "未知"} · {new Date(l.created_at).toLocaleString()}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Modal>

      {/* 历史学习记录弹窗 */}
      <Modal open={recordsOpen} onClose={() => setRecordsOpen(false)} title="历史学习记录">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <select
              className="rounded-md border bg-background px-2 py-1.5 text-sm"
              value={recYear}
              onChange={(e) => setRecYear(Number(e.target.value))}
            >
              {years.map((y) => (
                <option key={y} value={y}>{y} 年</option>
              ))}
            </select>
            <select
              className="rounded-md border bg-background px-2 py-1.5 text-sm"
              value={recMonth}
              onChange={(e) => setRecMonth(Number(e.target.value))}
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{m} 月</option>
              ))}
            </select>
            <select
              className="rounded-md border bg-background px-2 py-1.5 text-sm"
              value={recDay}
              onChange={(e) => setRecDay(Number(e.target.value))}
            >
              {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((d) => (
                <option key={d} value={d}>{d} 日</option>
              ))}
            </select>
            <Button onClick={queryRecords}>查询</Button>
          </div>
          {recordsError && <p className="text-sm text-destructive">{recordsError}</p>}
          {records && records.length === 0 && (
            <p className="text-sm text-muted-foreground">当天无学习记录</p>
          )}
          {records && records.length > 0 && (
            <ul className="max-h-[50vh] space-y-3 overflow-y-auto">
              {records.map((r) => (
                <li key={r.session_id} className="rounded-md border p-3">
                  <p className="text-sm font-medium">{r.task_title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {new Date(r.started_at).toLocaleString()}
                    {r.ended_at ? ` → ${new Date(r.ended_at).toLocaleString()}` : ""}
                  </p>
                  {r.reflection && (
                    <p className="mt-2 text-sm">感想：{r.reflection}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Modal>

      {/* 随机感想弹窗 */}
      <Modal open={reflectionOpen} onClose={() => setReflectionOpen(false)} title="随机回顾感想">
        {review ? (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">{review.date}</p>
            <p className="font-medium">{review.task_text}</p>
            <p className="text-sm">
              感想：{review.reflection ?? "（本场无感想）"}
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">暂无历史感想</p>
        )}
      </Modal>
    </div>
  )
}
