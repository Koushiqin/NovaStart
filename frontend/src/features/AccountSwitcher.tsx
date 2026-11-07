import { useEffect, useState } from "react"
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
  const [users, setUsers] = useState<DemoUser[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiClient
      .get<{ users: DemoUser[] }>("/users")
      .then((res) => setUsers(res.data.users))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">当前账号</span>
      {users.map((user) => (
        <Button
          key={user.id}
          size="sm"
          variant={user.id === userId ? "default" : "outline"}
          onClick={() => setUserId(user.id)}
        >
          {user.name}
        </Button>
      ))}
      {error && <span className="text-xs text-destructive">账号列表加载失败：{error}</span>}
    </div>
  )
}
