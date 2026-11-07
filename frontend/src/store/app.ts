import { create } from "zustand"
import { persist } from "zustand/middleware"

// 全局应用状态：当前用户、当前会话、服务端时钟偏移、结算步骤进度
interface AppState {
  userId: number | null
  currentSessionId: number | null
  serverTimeOffsetMs: number
  settleStep: number
  setUserId: (userId: number | null) => void
  setCurrentSessionId: (sessionId: number | null) => void
  setServerTimeOffsetMs: (ms: number) => void
  setSettleStep: (step: number) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      userId: null,
      currentSessionId: null,
      serverTimeOffsetMs: 0,
      settleStep: 0,
      setUserId: (userId) => set({ userId }),
      setCurrentSessionId: (currentSessionId) => set({ currentSessionId }),
      setServerTimeOffsetMs: (serverTimeOffsetMs) => set({ serverTimeOffsetMs }),
      setSettleStep: (settleStep) => set({ settleStep }),
    }),
    {
      // 只持久化身份；当前会话每次由 GET /sessions/current 重新确认，避免换库/换账号串号
      name: "novastart-user",
      partialize: ({ userId }) => ({ userId }),
    }
  )
)
