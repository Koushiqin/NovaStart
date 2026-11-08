import { create } from "zustand"
import { persist } from "zustand/middleware"

// 全局应用状态：当前用户、登录 token、当前会话、服务端时钟偏移、结算步骤进度
interface AppState {
  userId: number | null
  username: string | null
  sessionToken: string | null
  currentSessionId: number | null
  serverTimeOffsetMs: number
  settleStep: number
  login: (userId: number, username: string, token: string) => void
  logout: () => void
  setUserId: (userId: number | null) => void
  setCurrentSessionId: (sessionId: number | null) => void
  setServerTimeOffsetMs: (ms: number) => void
  setSettleStep: (step: number) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      userId: null,
      username: null,
      sessionToken: null,
      currentSessionId: null,
      serverTimeOffsetMs: 0,
      settleStep: 0,
      login: (userId, username, token) =>
        set({ userId, username, sessionToken: token, currentSessionId: null, settleStep: 0 }),
      logout: () =>
        set({ userId: null, username: null, sessionToken: null, currentSessionId: null, settleStep: 0 }),
      setUserId: (userId) => set({ userId }),
      setCurrentSessionId: (currentSessionId) => set({ currentSessionId }),
      setServerTimeOffsetMs: (serverTimeOffsetMs) => set({ serverTimeOffsetMs }),
      setSettleStep: (settleStep) => set({ settleStep }),
    }),
    {
      // 持久化身份与登录态；当前会话每次由 GET /sessions/current 重新确认
      name: "novastart-user",
      partialize: ({ userId, username, sessionToken }) => ({ userId, username, sessionToken }),
    }
  )
)
