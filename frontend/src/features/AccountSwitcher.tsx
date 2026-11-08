import { useNavigate } from "react-router-dom"
import { logout as logoutApi } from "@/api/auth"
import { useAppStore } from "@/store/app"

// 右上角账号区：未登录 → 登录/注册；已登录 → 用户名 + 切换账号 + 登出
export default function AccountSwitcher() {
  const navigate = useNavigate()
  const userId = useAppStore((s) => s.userId)
  const username = useAppStore((s) => s.username)
  const logoutStore = useAppStore((s) => s.logout)
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId)
  const setSettleStep = useAppStore((s) => s.setSettleStep)

  const handleLogout = async () => {
    try {
      await logoutApi()
    } catch {
      // 服务端 session 可能已过期，仍清本地
    }
    setCurrentSessionId(null)
    setSettleStep(0)
    logoutStore()
    navigate("/")
  }

  const textLink =
    "font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:text-foreground"

  return (
    <div className="flex items-center gap-3">
      {userId == null ? (
        <>
          <button type="button" className={textLink} onClick={() => navigate("/login")}>
            登录
          </button>
          <button type="button" className={textLink} onClick={() => navigate("/register")}>
            注册
          </button>
        </>
      ) : (
        <>
          <span className={`hidden sm:inline ${textLink}`}>{username}</span>
          <button type="button" className={textLink} onClick={() => navigate("/login")}>
            切换账号
          </button>
          <button type="button" className={textLink} onClick={handleLogout}>
            登出
          </button>
        </>
      )}
    </div>
  )
}
