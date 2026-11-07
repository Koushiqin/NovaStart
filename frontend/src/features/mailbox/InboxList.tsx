import { Button } from "@/components/ui/button"
import type { Letter } from "./types"

interface InboxListProps {
  letters: Letter[]
  busyId: number | null
  onFavorite: (id: number) => void
  onDismiss: (id: number) => void
}

// 未处理信箱列表（≤3）：每封可收藏 / 放弃；专注时投递的信打标签
export default function InboxList({ letters, busyId, onFavorite, onDismiss }: InboxListProps) {
  if (letters.length === 0) {
    return (
      <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
        现在没有等待你的信。
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
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => onFavorite(letter.id)}
              disabled={busyId !== null}
            >
              {busyId === letter.id ? "处理中…" : "收藏"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onDismiss(letter.id)}
              disabled={busyId !== null}
            >
              放弃
            </Button>
          </div>
        </li>
      ))}
    </ul>
  )
}
