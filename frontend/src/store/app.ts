import { create } from "zustand"
import { persist } from "zustand/middleware"

// 全局应用状态：当前用户、服务端时钟偏移、结算步骤进度
interface AppState {
  userId: number | null
  serverTimeOffsetMs: number
  settleStep: number
  setUserId: (userId: number | null) => void
  setServerTimeOffsetMs: (ms: number) => void
  setSettleStep: (step: number) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      userId: null,
      serverTimeOffsetMs: 0,
      settleStep: 0,
      setUserId: (userId) => set({ userId }),
      setServerTimeOffsetMs: (serverTimeOffsetMs) => set({ serverTimeOffsetMs }),
      setSettleStep: (settleStep) => set({ settleStep }),
    }),
    {
      // 只持久化身份；时钟偏移与结算进度每次会话重新计算，刷新后账号不回落默认
      name: "novastart-user",
      partialize: ({ userId }) => ({ userId }),
    }
  )
)
