import { useEffect, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import axios from "axios"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
import { useServerClock } from "@/hooks/useServerClock"
import { Button } from "@/components/ui/button"
import Modal from "@/components/ui/modal"
import TextEffect from "@/components/core/text-effect"
import Galaxy from "@/components/ui/galaxy"
import TaskComposer from "@/features/task/TaskComposer"
import SplitEditor from "@/features/task/SplitEditor"
import type { AnalyzeResult, TaskResponse, TodayResponse } from "@/features/task/types"
import StarWall, {
  CompactStarWallRenderer,
  type ProgressSummaryData,
} from "@/features/progress/StarWall"
import StreakBadge from "@/features/progress/StreakBadge"
import MailboxPanel from "@/features/mailbox/MailboxPanel"

interface CurrentSessionResponse {
  session: { id: number; ended_at: string | null } | null
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

const EYEBROW_CLASS =
  "font-sans text-[12px] font-black uppercase tracking-[0.14em] text-[rgba(245,244,248,0.45)]"
const LINK_CLASS =
  "font-display text-[18px] italic text-[rgba(245,244,248,0.72)] underline decoration-[rgba(217,211,228,0.3)] decoration-1 underline-offset-[6px] transition-colors hover:text-[#f5f4f8]"

// 首页：左对齐编辑式首屏 + 开始学习弹窗 + 右下天空（连续天数/星星墙）+ 三个历史功能弹窗
export default function HomePage() {
  const userId = useAppStore((s) => s.userId)
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId)
  const navigate = useNavigate()
  const location = useLocation()
  const clock = useServerClock()

  const [progress, setProgress] = useState<ProgressSummaryData | null>(null)
  const [today, setToday] = useState<TodayResponse | null>(null)
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState<"analyze" | "save" | "start" | null>(null)
  const [error, setError] = useState<string | null>(null)

  // 弹窗状态
  const [startOpen, setStartOpen] = useState(false)
  const [mailboxOpen, setMailboxOpen] = useState(false)
  const [recordsOpen, setRecordsOpen] = useState(false)
  const [reflectionOpen, setReflectionOpen] = useState(false)

  // 历史记录：年/月/日下拉（默认值取服务端校正后的当前日期，不用 new Date 直读）
  const [recYear, setRecYear] = useState<number>(() => clock.now().getFullYear())
  const [recMonth, setRecMonth] = useState<number>(() => clock.now().getMonth() + 1)
  const [recDay, setRecDay] = useState<number>(() => clock.now().getDate())
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
        // 今日任务已开始过：直接进入新目标输入态，不展示旧任务内容
        setInput(res.data.task?.locked ? "" : res.data.task?.raw_text ?? "")
      })
      .catch((e) => setError(errorMessage(e)))
  }, [startOpen, userId])

  // 从结算页点「再学一场」：回首页后自动打开弹窗（今日任务已开始，会直接进入新目标输入态）
  useEffect(() => {
    const state = location.state as { startNewTask?: boolean } | null
    if (!state?.startNewTask) return
    setStartOpen(true)
    // 清除导航状态，避免刷新或回退时重复弹窗
    navigate(location.pathname, { replace: true, state: null })
  }, [location.state, location.pathname, navigate])

  const stillCurrentAccount = (accountId: number | null) =>
    useAppStore.getState().userId === accountId

  // 开场前先确认是否有未走完流程的会话：进行中去专注页，已结束未结算去结算页
  const handleOpenStart = async () => {
    const accountId = userId
    if (accountId == null) return
    try {
      const res = await apiClient.get<CurrentSessionResponse>("/sessions/current")
      if (!stillCurrentAccount(accountId)) return
      const ongoing = res.data.session
      if (ongoing) {
        setCurrentSessionId(ongoing.id)
        navigate(ongoing.ended_at === null ? "/focus" : "/settle")
        return
      }
    } catch {
      // 查询失败不阻塞开场，仍按正常流程打开弹窗
    }
    setStartOpen(true)
  }

  const handleAnalyze = async () => {
    const text = input.trim()
    // 已开始的任务不可再改，直接走 POST /tasks 新建一条同日任务
    const existing = today?.task ?? null
    const task = existing?.locked ? null : existing
    if (!text) return
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
    const existing = today?.task ?? null
    const task = existing?.locked ? null : existing
    if (!task || !task.analyzed) return
    const accountId = userId
    setBusy("start")
    setError(null)
    try {
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

  // 当天任务已开始时视为没有可编辑任务，直接进入新目标输入态
  const task = today?.task?.locked ? null : (today?.task ?? null)

  const currentYear = clock.now().getFullYear()
  const years = Array.from({ length: 10 }, (_, i) => currentYear - 5 + i)
  const daysInMonth = new Date(recYear, recMonth, 0).getDate()

  return (
    <div className="cosmos-sky relative min-h-screen">
      {/* 交互式星场：纯装饰层，不接收交互，鼠标事件由组件在 window 上监听 */}
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        <Galaxy
          density={1}
          glowIntensity={0.3}
          flareIntensity={1}
          starSpeed={0.5}
          mouseRepulsion
          clickWarp
        />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-[1200px] flex-col px-6 pb-12 pt-24 sm:px-10 sm:pb-16 sm:pt-28">
        {/* 左上 wordmark */}
        <div className="flex items-center gap-3">
          <span className="h-1.5 w-1.5 rounded-full bg-[#f5f4f8]" aria-hidden="true" />
          <span className="font-sans text-[13px] font-semibold uppercase tracking-[0.42em] text-[#f5f4f8]">
            NovaStart
          </span>
        </div>

        <div className="mt-14 grid flex-1 content-between gap-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.62fr)] lg:gap-20">
          {/* 左列：标题 → 简介 → 主 CTA → 历史入口 */}
          <div className="flex max-w-[34rem] flex-col justify-between gap-12">
            <div>
              <p className={EYEBROW_CLASS}>DAILY PRACTICE · FIVE MINUTES</p>
              <h1 className="mt-7 font-display text-[clamp(2.6rem,6.2vw,5rem)] leading-[0.9] tracking-[-0.01em] text-[#f5f4f8]">
                <span className="block italic">
                  <TextEffect per="char" preset="fade">
                    Five minutes a day.
                  </TextEffect>
                </span>
                <span className="block italic text-[rgba(245,244,248,0.6)]">
                  <TextEffect per="char" preset="fade" delay={0.45}>
                    Learn a little, on purpose.
                  </TextEffect>
                </span>
              </h1>
              <p className="mt-7 max-w-[27rem] text-justify text-[15px] leading-[1.7] text-[rgba(245,244,248,0.65)]">
                Five minutes, one concrete step — so “I want to learn” becomes something you
                finish today.
              </p>
            </div>

            <div className="flex flex-col items-start gap-8">
              <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:gap-6">
                <Button
                  variant="frost"
                  disabled={userId == null}
                  onClick={() => void handleOpenStart()}
                  className="h-32 w-32 px-0 text-[12px] font-semibold uppercase tracking-[0.16em]"
                >
                  Start learning
                </Button>
                <p className="max-w-[15rem] text-[12px] leading-relaxed text-[rgba(245,244,248,0.4)]">
                  A letter from a stranger arrives after your five minutes.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
                <button
                  type="button"
                  className={LINK_CLASS}
                  onClick={() => setMailboxOpen(true)}
                >
                  Mailbox
                </button>
                <button
                  type="button"
                  className={LINK_CLASS}
                  onClick={() => {
                    setRecordsOpen(true)
                    setRecords(null)
                    setRecordsError(null)
                  }}
                >
                  Learning log
                </button>
                <button
                  type="button"
                  className={LINK_CLASS}
                  onClick={() => {
                    setReflectionOpen(true)
                    void loadReview()
                  }}
                >
                  Random reflection
                </button>
              </div>
            </div>
          </div>

          {/* 右列：天空（连续天数 + 30 天星星点云） */}
          <div className="flex flex-col gap-4 lg:items-end lg:justify-end">
            <p className={EYEBROW_CLASS}>YOUR SKY</p>
            {progress !== null ? (
              <>
                <StreakBadge
                  current={progress.streak.current}
                  longest={progress.streak.longest}
                />
                <StarWall wall={progress.wall} renderer={CompactStarWallRenderer} />
              </>
            ) : (
              <p className="max-w-[16rem] text-[13px] leading-relaxed text-[rgba(245,244,248,0.45)] lg:text-right">
                {userId == null
                  ? "Sign in to keep a sky of your own — one five-minute step at a time."
                  : "Your first five minutes will light the first star."}
              </p>
            )}
          </div>
        </div>
      </div>

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
                disabled={busy === "analyze"}
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
                {busy === "start" ? "进入中…" : "开始学习"}
              </Button>
            </>
          )}
          {error && <p className="text-sm text-destructive">请求失败：{error}</p>}
        </div>
      </Modal>

      {/* 信箱弹窗：未处理 / 历史 / 发出记录 */}
      <Modal
        open={mailboxOpen}
        onClose={() => setMailboxOpen(false)}
        title="信箱"
        maxWidth="max-w-2xl"
      >
        <div className="max-h-[65vh] overflow-y-auto pr-1">
          <MailboxPanel />
        </div>
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
