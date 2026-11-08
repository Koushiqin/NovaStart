import { useNavigate } from "react-router-dom"
import { logout as logoutApi } from "@/api/auth"
import { useAppStore } from "@/store/app"
import { Button } from "@/components/ui/button"

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

  return (
    <div className="flex items-center gap-2">
      {userId == null ? (
        <>
          <Button size="sm" variant="outline" onClick={() => navigate("/login")}>
            登录
          </Button>
          <Button size="sm" onClick={() => navigate("/register")}>
            注册
          </Button>
        </>
      ) : (
        <>
          <span className="text-sm text-muted-foreground">{username}</span>
          <Button size="sm" variant="outline" onClick={() => navigate("/login")}>
            切换账号
          </Button>
          <Button size="sm" variant="ghost" onClick={handleLogout}>
            登出
          </Button>
        </>
      )}
    </div>
  )
}
