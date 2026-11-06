import { create } from "zustand"

// 全局应用状态：当前用户、服务端时钟偏移、结算步骤进度
interface AppState {
  userId: number | null
  serverTimeOffsetMs: number
  settleStep: number
  setUserId: (userId: number | null) => void
  setServerTimeOffsetMs: (ms: number) => void
  setSettleStep: (step: number) => void
}

export const useAppStore = create<AppState>((set) => ({
  userId: null,
  serverTimeOffsetMs: 0,
  settleStep: 0,
  setUserId: (userId) => set({ userId }),
  setServerTimeOffsetMs: (serverTimeOffsetMs) => set({ serverTimeOffsetMs }),
  setSettleStep: (settleStep) => set({ settleStep }),
}))
