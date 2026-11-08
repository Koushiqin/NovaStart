import { useState } from "react"
import axios from "axios"
import { apiClient } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

interface StepProps {
  sessionId: number
  onDone: () => void
}

// 第①步：感想选填、上限 200 字、只写一次；空白 = 跳过（后端不落库但推进断点）
export default function StepReflection({ sessionId, onDone }: StepProps) {
  const [content, setContent] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (value: string) => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await apiClient.post(`/sessions/${sessionId}/reflection`, { content: value })
      onDone()
    } catch (e) {
      // 409 = 已提交或已跳过：断点已在下一步，刷新后继续即可
      if (axios.isAxiosError(e) && e.response?.status === 409) {
        onDone()
        return
      }
      setError("提交失败，请稍后重试")
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
          STEP 01 · REFLECT
        </p>
        <CardTitle>第①步 · 写一句感想</CardTitle>
        <CardDescription>选填。写一句就好，也可以跳过；提交后不可修改。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <textarea
          className="min-h-28 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
          maxLength={200}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="这一场里，你注意到了什么？"
          disabled={busy}
        />
        <Button className="w-full" onClick={() => submit(content)} disabled={busy}>
          {busy ? "提交中…" : "提交感想"}
        </Button>
        <Button className="w-full" variant="outline" onClick={() => submit("")} disabled={busy}>
          跳过
        </Button>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  )
}
