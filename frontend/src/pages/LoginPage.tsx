import { useState } from "react"
import axios from "axios"
import { useNavigate, Link } from "react-router-dom"
import { login } from "@/api/auth"
import { useAppStore } from "@/store/app"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export default function LoginPage() {
  const navigate = useNavigate()
  const loginStore = useAppStore((s) => s.login)
  const [username, setUsername] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = username.trim()
    if (!trimmed) {
      setError("请输入用户名")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const res = await login(trimmed)
      loginStore(res.user.id, res.user.username, res.token)
      navigate("/")
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null
      if (detail && typeof detail === "object" && "message" in detail) {
        setError(String(detail.message))
      } else if (detail && typeof detail === "string") {
        setError(detail)
      } else {
        setError("登录失败，请重试")
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-[70vh] items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>登录 NovaStart</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">用户名</label>
              <input
                className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="输入用户名"
                autoFocus
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "登录中…" : "登录"}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              还没有账号？{" "}
              <Link to="/register" className="text-primary underline">
                注册
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
