import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

// 与 backend/app/schemas/progress.py 的 ProgressSummary 对应（首页进度区唯一数据源）
export type WallState = "lit" | "dim" | "broken" | "empty"

export interface WallDay {
  date: string
  state: WallState
  level: number | null
}

export interface ProgressSummaryData {
  today: { minutes: number; level: number }
  streak: { current: number; longest: number; was_reset: boolean }
  wall: WallDay[]
  server_time: string
}

const STAR_PATH =
  "M12 2.5l2.94 5.96 6.58.96-4.76 4.64 1.12 6.55L12 17.52 6.12 20.6l1.12-6.55-4.76-4.64 6.58-.96L12 2.5z"

// 亮度三档与暗/空心统一由 index.css 的 --star-* 变量决定，组件内不出现写死色值
const LIT_FILL: Record<number, string> = {
  1: "fill-[var(--star-level-1)]",
  2: "fill-[var(--star-level-2)]",
  3: "fill-[var(--star-level-3)]",
}

interface StarIconProps {
  variant: WallState
  level?: number | null
  className?: string
  glow?: boolean
}

// 星星图形（星星墙 / 结算页 / 里程碑共用），只负责画，不推算任何天数或亮度
export function StarIcon({ variant, level, className, glow = false }: StarIconProps) {
  const fill =
    variant === "lit" ? LIT_FILL[level ?? 3] ?? LIT_FILL[3] : variant === "dim" ? "fill-[var(--star-dim)]" : "fill-none"

  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden
      className={cn(
        "shrink-0",
        fill,
        variant === "broken" && "stroke-[var(--star-broken)]",
        glow && "drop-shadow-[0_0_8px_var(--star-level-2)]",
        className
      )}
    >
      <path d={STAR_PATH} strokeWidth={variant === "broken" ? 1.5 : 0} />
    </svg>
  )
}

const STATE_LABEL: Record<WallState, string> = {
  lit: "已点亮",
  dim: "今天还没点亮",
  broken: "断签",
  empty: "",
}

/**
 * 星星墙渲染器契约：美化时只需实现本接口并在调用处传入 renderer，
 * 数据来源（GET /api/progress/summary）与 state/level 语义不得改动。
 */
export interface StarWallRendererProps {
  wall: WallDay[]
}

export type StarWallRenderer = (props: StarWallRendererProps) => ReactNode

// 默认渲染：最近 30 天星星墙，服务端给出 state/level，前端只做三态渲染（empty 不绘制）
export function DefaultStarWallRenderer({ wall }: StarWallRendererProps) {
  return (
    <div className="grid grid-cols-10 justify-items-center gap-x-2 gap-y-2" aria-label="最近 30 天星星墙">
      {wall.map((day) => {
        if (day.state === "empty") {
          return <span key={day.date} className="block h-4 w-4" aria-hidden />
        }
        return (
          <span
            key={day.date}
            className="flex h-4 w-4 items-center justify-center"
            title={`${day.date} ${STATE_LABEL[day.state]}`}
          >
            <StarIcon variant={day.state} level={day.level} className="h-4 w-4" />
          </span>
        )
      })}
    </div>
  )
}

/**
 * 星星墙容器：只负责把数据交给渲染器。
 * 预留美化接口 renderer，默认使用 DefaultStarWallRenderer；
 * 换皮时新增一个满足 StarWallRenderer 的组件并从调用处注入即可。
 */
export default function StarWall({
  wall,
  renderer: Renderer = DefaultStarWallRenderer,
}: StarWallRendererProps & { renderer?: StarWallRenderer }) {
  return <Renderer wall={wall} />
}
