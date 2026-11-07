import type { OutboxLetter } from "./types"

// 发出记录：自己投出的信，按状态标「已投递 / 未送达」
export default function OutboxList({ letters }: { letters: OutboxLetter[] }) {
  if (letters.length === 0) {
    return (
      <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
        还没有寄出过信。
      </p>
    )
  }

  return (
    <ul className="space-y-3">
      {letters.map((letter) => (
        <li key={letter.id} className="rounded-md border p-3 space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">寄给 {letter.recipient_name ?? "同学"}</span>
            <span className={letter.status === "delivered" ? "text-muted-foreground" : "text-destructive"}>
              {letter.status === "delivered" ? "已投递" : "未送达"}
            </span>
          </div>
          <p className="text-sm leading-relaxed">{letter.content}</p>
        </li>
      ))}
    </ul>
  )
}
