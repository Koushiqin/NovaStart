import SmokePanel from "@/features/SmokePanel"

// 首页：当前挂端到端冒烟面板，验证前后端垂直切片
export default function HomePage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <SmokePanel />
    </div>
  )
}
