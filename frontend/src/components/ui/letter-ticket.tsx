import type { ReactNode } from "react"

export interface LetterTicketProps {
  id: number
  dateISO: string
  content: string
  counterpart: string | null
  direction: "in" | "out"
  status?: string
  actions?: ReactNode
}

// 纯展示票据：主票（方向标签 + 人名 + 日期 + 正文 + 操作）+ 存根（编号 + 日期）
function formatDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${date.getFullYear()}.${month}.${day}`
}

export default function LetterTicket({
  id,
  dateISO,
  content,
  counterpart,
  direction,
  status,
  actions,
}: LetterTicketProps) {
  const label = direction === "in" ? "FROM" : "TO"

  return (
    <div className="relative flex max-w-sm flex-col overflow-hidden rounded-2xl border border-border/70 bg-surface-2 sm:flex-row">
      <div className="min-w-0 flex-1 space-y-3 px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
              {label}
            </p>
            <p className="text-sm text-foreground">{counterpart ?? "同学"}</p>
          </div>
          <div className="shrink-0 text-right">
            <p className="font-mono text-[11px] tabular-nums text-muted-foreground">
              {formatDate(dateISO)}
            </p>
            {status && (
              <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                {status}
              </p>
            )}
          </div>
        </div>
        <p className="text-sm leading-relaxed text-foreground">{content}</p>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      <div className="relative shrink-0 border-t border-dashed border-border/70 px-5 py-4 sm:w-32 sm:border-l sm:border-t-0">
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -left-2 -top-2 h-4 w-4 rounded-full bg-background"
        />
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -right-2 -top-2 h-4 w-4 rounded-full bg-background sm:-bottom-2 sm:-left-2 sm:right-auto sm:top-auto"
        />
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          NO. {String(id).padStart(4, "0")}
        </p>
        <p className="mt-2 font-mono text-[11px] tabular-nums text-muted-foreground">
          {formatDate(dateISO)}
        </p>
      </div>
    </div>
  )
}
