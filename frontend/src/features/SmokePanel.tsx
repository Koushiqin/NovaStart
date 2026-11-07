import { useEffect, useReducer, useState } from "react"
import axios from "axios"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
import { useServerClock } from "@/hooks/useServerClock"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

interface ResetSeedResponse {
  users: { id: number; name: string }[]
}

// 端到端冒烟面板（临时验证组件，后续被正式组件替换）：
// 建示例任务 → 开始专注 → 用 server_time 校正后的时钟渲染正计时
export default function SmokePanel() {
  const [loading, setLoading] = useState(false)
  const [starterStep, setStarterStep] = useState<string | null>(null)
  const [startedAt, setStartedAt] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [, forceTick] = useReducer((x: number) => x + 1, 0)
  const setUserId = useAppStore((s) => s.setUserId)
  const { now } = useServerClock()

  // 开场后每秒触发一次重渲染，驱动正计时与 server_time 显示
  useEffect(() => {
    if (!startedAt) return
    const timer = setInterval(forceTick, 1000)
    return () => clearInterval(timer)
  }, [startedAt])

  const handleStart = async () => {
    setLoading(true)
    setError(null)
    try {
      // 已选账号时按当前账号建任务；未选账号时重置种子并选第一个演示账号
      if (useAppStore.getState().userId == null) {
        const seed = await axios.post<ResetSeedResponse>("/dev/reset-seed")
        setUserId(seed.data.users[0].id)
      }
      // 依次调 POST /tasks + POST /sessions（垂直切片），身份经请求头自动注入
      const task = await apiClient.post("/tasks", { raw_text: "读完产品文档第 3 章" })
      setStarterStep(task.data.starter_step)
      const session = await apiClient.post("/sessions", { task_id: task.data.task_id })
      setStartedAt(new Date(session.data.started_at))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const elapsedSec = startedAt
    ? Math.max(0, Math.floor((now().getTime() - startedAt.getTime()) / 1000))
    : 0
  const mm = String(Math.floor(elapsedSec / 60)).padStart(2, "0")
  const ss = String(elapsedSec % 60).padStart(2, "0")

  return (
    <Card className="w-[420px]">
      <CardHeader>
        <CardTitle>端到端冒烟</CardTitle>
        <CardDescription>建任务 → 开始专注 → 正计时（server_time 校正）</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={handleStart} disabled={loading}>
          {loading ? "请求中…" : "建示例任务并开场"}
        </Button>
        {error && <p className="text-sm text-destructive">请求失败：{error}</p>}
        {starterStep && <p className="text-sm">starter_step：{starterStep}</p>}
        {startedAt && (
          <>
            <p className="text-3xl font-mono tabular-nums">
              {mm}:{ss}
            </p>
            <p className="text-xs text-muted-foreground">
              server_time: {now().toISOString()}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
