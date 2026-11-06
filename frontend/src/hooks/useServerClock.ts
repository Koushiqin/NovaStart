import { useAppStore } from "@/store/app"

// 前端唯一取时间入口：本地时钟 + 服务端偏移校正（客户端时钟不可信，Review Focus #1）
export function useServerClock() {
  const offsetMs = useAppStore((s) => s.serverTimeOffsetMs)
  return {
    now: () => new Date(Date.now() + offsetMs),
  }
}
