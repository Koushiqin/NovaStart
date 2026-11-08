import { useState } from "react"
import axios from "axios"
import { useNavigate, Link } from "react-router-dom"
import { register } from "@/api/auth"
import { useAppStore } from "@/store/app"
import MeteorField from "@/components/ui/meteor-field"

export default function RegisterPage() {
  const navigate = useNavigate()
  const loginStore = useAppStore((s) => s.login)
  const [username, setUsername] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = username.trim()
    if (trimmed.length < 1 || trimmed.length > 15) {
      setError("用户名长度需为 1-15 个字符")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const res = await register(trimmed)
      loginStore(res.user.id, res.user.username, res.token)
      navigate("/")
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null
      if (detail && typeof detail === "object" && "message" in detail) {
        setError(String(detail.message))
      } else if (Array.isArray(detail)) {
        setError("用户名不合法，请调整后重试")
      } else {
        setError("注册失败，请重试")
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6">
      <MeteorField />
      <div className="glass-form relative z-10 w-full max-w-sm rounded-2xl p-8">
        <div className="text-center">
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-sky-200/70">
            SIGN UP
          </p>
          <h1
            className="mt-2 text-3xl font-extrabold uppercase tracking-[0.2em] text-transparent"
            style={{ WebkitTextStroke: "1px #ffffff" }}
          >
            NOVASTART
          </h1>
          <p className="mt-2 text-sm text-white/60">创建账号，开始你的五分钟。</p>
        </div>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-white/80">用户名（1-15 字符）</label>
            <input
              className="w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2 text-sm text-white outline-none transition-colors placeholder:text-white/40 focus:border-white/60 focus:ring-2 focus:ring-ring"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="设置用户名"
              autoFocus
              maxLength={15}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <button type="submit" className="glass-submit" disabled={busy}>
            {busy ? "注册中…" : "注册并登录"}
          </button>
          <p className="text-center text-sm text-white/60">
            已有账号？{" "}
            <Link to="/login" className="text-white underline underline-offset-4">
              登录
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
