import { Button } from "@/components/ui/button"
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
        <li key={letter.id} className="rounded-md border p-3 space-y-2">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{letter.sender_name ?? "同学"} 寄来</span>
            {letter.focused_delivery && (
              <span className="text-xs text-muted-foreground">专注时投递</span>
            )}
          </div>
          <p className="text-sm leading-relaxed">{letter.content}</p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onDelete(letter.id)}
            disabled={busyId !== null}
          >
            {busyId === letter.id ? "删除中…" : "删除"}
          </Button>
        </li>
      ))}
    </ul>
  )
}
