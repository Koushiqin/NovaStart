import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { CarryOver } from "@/features/task/types"

// 示例标签：点击只预填输入，不触发分析（只有点「分析」才调模型）
const EXAMPLES = ["背 20 个单词", "复习三角函数", "改一段代码", "读 10 页书"]

const MAX_LENGTH = 200

interface TaskComposerProps {
  value: string
  onChange: (value: string) => void
  onAnalyze: () => void
  analyzing: boolean
  /** 未选账号或任务已锁定：禁用输入与分析 */
  disabled: boolean
  carryOver: CarryOver | null
  onContinueYesterday: () => void
}

export default function TaskComposer({
  value,
  onChange,
  onAnalyze,
  analyzing,
  disabled,
  carryOver,
  onContinueYesterday,
}: TaskComposerProps) {
  const canAnalyze = !disabled && !analyzing && value.trim().length > 0

  return (
    <div className="space-y-4">
      {carryOver && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-sm">
          <span>
            昨天没走完，今天要不要接着来？
            <span className="ml-2 text-muted-foreground">「{carryOver.raw_text}」</span>
          </span>
          <Button size="sm" variant="outline" onClick={onContinueYesterday} disabled={disabled}>
            接着来
          </Button>
        </div>
      )}

      <div className="space-y-2">
        <label htmlFor="task-input" className="text-sm font-medium">
          今天想学什么
        </label>
        <input
          id="task-input"
          type="text"
          value={value}
          maxLength={MAX_LENGTH}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          placeholder="用一句话说清楚，比如：背 20 个单词"
          className={cn(
            "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
            "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-50"
          )}
        />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>最多 {MAX_LENGTH} 字</span>
          <span className="tabular-nums">
            {value.length}/{MAX_LENGTH}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((example) => (
          <Button
            key={example}
            size="sm"
            variant="secondary"
            onClick={() => onChange(example)}
            disabled={disabled}
          >
            {example}
          </Button>
        ))}
      </div>

      <Button onClick={onAnalyze} disabled={!canAnalyze} className="w-full">
        {analyzing ? "分析中…" : "分析"}
      </Button>
    </div>
  )
}
