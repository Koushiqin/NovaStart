import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { TaskState } from "@/features/task/types"

interface SplitEditorProps {
  task: TaskState
  saving: boolean
  onUpdate: (patch: { starter_step?: string; steps?: string[] }) => void
}

const INPUT_CLASS = cn(
  "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm",
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
  "disabled:cursor-not-allowed disabled:opacity-50"
)

// 展示与编辑当前采用版 starter / steps；原始版只用于结算复述（P4），此处不显示
export default function SplitEditor({ task, saving, onUpdate }: SplitEditorProps) {
  const [starter, setStarter] = useState(task.starter_step)
  const [steps, setSteps] = useState(task.steps)

  // 服务端值变化（重新分析 / 切换账号 / 保存成功）时同步本地编辑态
  useEffect(() => {
    setStarter(task.starter_step)
    setSteps(task.steps)
  }, [task.starter_step, task.steps])

  const locked = task.locked

  const commitStarter = () => {
    const trimmed = starter.trim()
    if (!trimmed || trimmed === task.starter_step) {
      setStarter(task.starter_step)
      return
    }
    onUpdate({ starter_step: trimmed })
  }

  const commitStep = (index: number) => {
    const trimmed = steps[index]?.trim() ?? ""
    if (!trimmed) {
      setSteps(task.steps)
      return
    }
    const next = steps.map((step, i) => (i === index ? trimmed : step.trim()))
    if (next.every((step, i) => step === task.steps[i])) return
    onUpdate({ steps: next })
  }

  const removeStep = (index: number) => {
    onUpdate({ steps: steps.filter((_, i) => i !== index) })
  }

  return (
    <div className="space-y-4">
      {task.source === "fallback" && (
        <p className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
          智能拆分暂不可用，先用通用路线。
        </p>
      )}

      {task.split_stale && (
        <p className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
          标题已修改，可重新分析。
        </p>
      )}

      {locked && (
        <p className="text-xs text-muted-foreground">已开始学习，任务内容已锁定。</p>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">第一步（5 分钟内完成）</span>
          {saving && <span className="text-xs text-muted-foreground">保存中…</span>}
        </div>
        <input
          value={starter}
          onChange={(event) => setStarter(event.target.value)}
          onBlur={commitStarter}
          disabled={locked}
          className={INPUT_CLASS}
        />
      </div>

      <div className="space-y-2">
        <span className="text-sm font-medium">后续步骤</span>
        {steps.length === 0 ? (
          <p className="text-xs text-muted-foreground">暂无后续步骤。</p>
        ) : (
          steps.map((step, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                value={step}
                maxLength={200}
                onChange={(event) =>
                  setSteps((prev) => prev.map((s, i) => (i === index ? event.target.value : s)))
                }
                onBlur={() => commitStep(index)}
                disabled={locked}
                className={INPUT_CLASS}
              />
              <Button
                size="sm"
                variant="ghost"
                onClick={() => removeStep(index)}
                disabled={locked}
              >
                删除
              </Button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
