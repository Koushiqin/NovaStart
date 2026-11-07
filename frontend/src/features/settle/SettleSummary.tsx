import { Card, CardContent } from "@/components/ui/card"

// 与 backend/app/schemas/session.py 的 SessionSummary 对应（结算页唯一数据源）
export interface SettleSummaryData {
  duration_sec: number
  today_total_sec: number
  task_text: string
  starter_text: string
  settle_step: number
  status: string
  received_during_session: number
  star_level: number | null
  streak: number | null
  server_time: string
}

function minutes(seconds: number): number {
  return Math.floor(seconds / 60)
}

// 三段式摘要：具体成果（本次时长 + 今天累计）与 starter 原话复述；
// star_level / streak 槽位由 P5 填充，无值时不伪造数字或文案。
export default function SettleSummary({ data }: { data: SettleSummaryData }) {
  return (
    <Card>
      <CardContent className="space-y-5 p-6 text-center">
        <p className="text-2xl font-semibold">
          本次 {minutes(data.duration_sec)} 分钟
          <span className="text-muted-foreground">
            {" "}
            · 今天累计 {minutes(data.today_total_sec)} 分钟
          </span>
        </p>

        <div className="space-y-1">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">你的起步动作</p>
          <p className="text-lg font-medium leading-relaxed">「{data.starter_text}」</p>
        </div>

        {/* P5 替换点：星星亮度 / 连续天数槽位 */}
        {(data.star_level !== null || data.streak !== null) && (
          <div className="flex justify-center gap-6 text-sm text-muted-foreground">
            {data.star_level !== null && <span>星星 {data.star_level}</span>}
            {data.streak !== null && <span>连续 {data.streak} 天</span>}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
