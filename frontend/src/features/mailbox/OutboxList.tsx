import LetterTicket from "@/components/ui/letter-ticket"
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
        <li key={letter.id}>
          <LetterTicket
            id={letter.id}
            dateISO={letter.created_at}
            content={letter.content}
            counterpart={letter.recipient_name}
            direction="out"
            status={letter.status === "delivered" ? "已投递" : "未送达"}
          />
        </li>
      ))}
    </ul>
  )
}
