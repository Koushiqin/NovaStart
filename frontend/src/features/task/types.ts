// 与 backend/app/schemas/task.py 一一对应的前端契约类型（唯一入口，避免各组件各写一份）

export type StepSource = "llm" | "mock" | "fallback"

export interface TaskState {
  id: number
  raw_text: string
  starter_step: string
  steps: string[]
  origin_starter_step: string | null
  origin_steps: string[] | null
  analyzed: boolean
  split_stale: boolean
  locked: boolean
  source: StepSource | null
}

export interface TaskResponse {
  task: TaskState
  server_time: string
}

export interface AnalyzeResult {
  starter_step: string
  steps: string[]
  source: StepSource
  server_time: string
}

export interface CarryOver {
  raw_text: string
  date: string
}

export interface TodayResponse {
  task: TaskState | null
  carry_over: CarryOver | null
  server_time: string
}
