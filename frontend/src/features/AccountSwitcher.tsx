import { useCallback, useEffect, useState } from "react"
import { apiClient } from "@/api/client"
import { useAppStore } from "@/store/app"
import { Button } from "@/components/ui/button"

interface DemoUser {
  id: number
  name: string
}

// 演示账号切换器：拉取 GET /api/users，点击按钮即切换全局身份（持久化到 localStorage）
export default function AccountSwitcher() {
  const userId = useAppStore((s) => s.userId)
  const setUserId = useAppStore((s) => s.setUserId)
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId)
  const setSettleStep = useAppStore((s) => s.setSettleStep)
  const [users, setUsers] = useState<DemoUser[]>([])
  const [error, setError] = useState<string | null>(null)
  const [resetting, setResetting] = useState(false)

  // 切账号先清空上一账号的会话/结算进度，避免结算页拉到旧账号的会话
  const handleSwitch = (nextUserId: number) => {
    setCurrentSessionId(null)
    setSettleStep(0)
    setUserId(nextUserId)
  }

  const loadUsers = useCallback(async () => {
    try {
      const res = await apiClient.get<{ users: DemoUser[] }>("/users")
      setUsers(res.data.users)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void loadUsers()
  }, [loadUsers])

  // 空库自服务：Demo 无生产环境，直接重置种子数据
  const handleResetSeed = async () => {
    setResetting(true)
    setError(null)
    try {
      await apiClient.post("/dev/reset-seed", null, { baseURL: "" })
      await loadUsers()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">当前账号</span>
      {users.map((user) => (
        <Button
          key={user.id}
          size="sm"
          variant={user.id === userId ? "default" : "outline"}
          onClick={() => handleSwitch(user.id)}
        >
          {user.name}
        </Button>
      ))}
      {users.length === 0 && !error && (
        <Button size="sm" variant="outline" onClick={handleResetSeed} disabled={resetting}>
          {resetting ? "初始化中…" : "初始化演示数据"}
        </Button>
      )}
      {error && <span className="text-xs text-destructive">账号列表加载失败：{error}</span>}
    </div>
  )
}
