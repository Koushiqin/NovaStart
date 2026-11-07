import axios from "axios"
import { useAppStore } from "@/store/app"

// 统一 axios 实例：baseURL=/api，vite dev 下经 proxy 转发到后端 8000，Docker 下由 nginx 反代
export const apiClient = axios.create({ baseURL: "/api" })

// 请求拦截器：所有 /api 请求单点注入身份请求头，身份唯一来源是 store.userId
apiClient.interceptors.request.use((config) => {
  const id = useAppStore.getState().userId
  if (id != null) config.headers["X-User-Id"] = String(id)
  return config
})

// 响应拦截器：读取服务端 server_time，记录服务端与本地时钟的偏移量（客户端时钟不可信）
apiClient.interceptors.response.use((response) => {
  const serverTime = response.data?.server_time
  if (typeof serverTime === "string") {
    const offsetMs = new Date(serverTime).getTime() - Date.now()
    useAppStore.getState().setServerTimeOffsetMs(offsetMs)
  }
  return response
})
