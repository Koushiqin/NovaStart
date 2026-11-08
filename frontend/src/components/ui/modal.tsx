import { type ReactNode, useEffect } from "react"
import { X } from "lucide-react"
import { Button } from "./button"

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
  maxWidth?: string
}

// 轻量弹窗：遮罩 + 居中卡片 + 右上角关闭按钮。不引入 radix 依赖。
export default function Modal({ open, onClose, title, children, maxWidth = "max-w-lg" }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className={`relative z-10 w-full ${maxWidth} animate-in fade-in zoom-in-95 border border-[rgba(217,211,228,0.12)] bg-[rgba(3,2,6,0.55)] p-6 backdrop-blur-2xl duration-200`}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <p className="font-sans text-[11px] font-black uppercase tracking-[0.14em] text-[rgba(245,244,248,0.4)]">
              NOVASTART
            </p>
            {title && <h2 className="mt-1 text-lg font-semibold">{title}</h2>}
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="关闭">
            <X className="h-4 w-4" />
          </Button>
        </div>
        {children}
      </div>
    </div>
  )
}
