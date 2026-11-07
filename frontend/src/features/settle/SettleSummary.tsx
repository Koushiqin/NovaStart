import { motion } from "framer-motion"
import { Card, CardContent } from "@/components/ui/card"
import { StarIcon } from "@/features/progress/StarWall"

export interface StreakInfo {
  current: number
  longest: number
  was_reset: boolean
}

// 与 backend/app/schemas/session.py 的 SessionSummary 对应（结算页唯一数据源）
export interface SettleSummaryData {
  duration_sec: number
  today_total_sec: number
  attribution_date: string
  task_text: string
  starter_text: string
  settle_step: number
  status: string
  received_during_session: number
  star_level: number | null
  streak: StreakInfo | null
  server_time: string
}

function minutes(seconds: number): number {
  return Math.floor(seconds / 60)
}

// 归属日 ISO（YYYY-MM-DD）→ 「M月D日」：跨零点结算时标签必须显示归属日，不能写「今天/当日」
function dayLabel(iso: string): string {
  const [, month, day] = iso.split("-")
  return `${Number(month)}月${Number(day)}日`
}

// 三段式摘要：具体成果（本次时长 + 归属日累计）、starter 原话复述，
// 以及 P5 填入的星星点亮动画与连续天数；无值时不伪造数字或文案。
export default function SettleSummary({ data }: { data: SettleSummaryData }) {
  return (
    <Card>
      <CardContent className="space-y-5 p-6 text-center">
        <p className="text-2xl font-semibold">
          本次 {minutes(data.duration_sec)} 分钟
          <span className="text-muted-foreground">
            {" "}
            · {dayLabel(data.attribution_date)}累计 {minutes(data.today_total_sec)} 分钟
          </span>
        </p>

        <div className="space-y-1">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">你的起步动作</p>
          <p className="text-lg font-medium leading-relaxed">「{data.starter_text}」</p>
        </div>

        {data.star_level !== null && (
          <motion.div
            className="flex justify-center"
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          >
            <StarIcon variant="lit" level={data.star_level} glow className="h-12 w-12" />
          </motion.div>
        )}

        {data.received_during_session > 0 && (
          <p className="text-sm text-muted-foreground">
            你专注时收到 {data.received_during_session} 封信
          </p>
        )}

        {data.streak !== null && data.streak.current > 0 && (
          <div className="space-y-1">
            <p className="text-3xl font-semibold tabular-nums">
              连续 {data.streak.current} 天
            </p>
            <p className="text-xs text-muted-foreground">历史最长 {data.streak.longest} 天</p>
            <p className="text-sm text-muted-foreground">
              {data.streak.was_reset
                ? "新的一条线，从今天这 5 分钟开始。"
                : "明天再来 5 分钟，让下一颗星星接着亮。"}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
