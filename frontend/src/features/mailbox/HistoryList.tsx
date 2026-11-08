import { Button } from "@/components/ui/button"
import LetterTicket from "@/components/ui/letter-ticket"
import type { Letter } from "./types"

interface HistoryListProps {
  letters: Letter[]
  busyId: number | null
  onDelete: (id: number) => void
}

// 历史信箱：只有收藏的信；可随时手动删除
export default function HistoryList({ letters, busyId, onDelete }: HistoryListProps) {
  if (letters.length === 0) {
    return (
      <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
        收藏的信会留在这里。
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
            counterpart={letter.sender_name}
            direction="in"
            status={letter.focused_delivery ? "专注时投递" : undefined}
            actions={
              <Button
                size="sm"
                variant="outline"
                onClick={() => onDelete(letter.id)}
                disabled={busyId !== null}
              >
                {busyId === letter.id ? "删除中…" : "删除"}
              </Button>
            }
          />
        </li>
      ))}
    </ul>
  )
}
