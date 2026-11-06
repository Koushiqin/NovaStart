import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

// 脚手架占位页：验证 Tailwind + shadcn/ui 源码组件可用，Task 11 替换为正式首页
function App() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <Card className="w-[360px]">
        <CardHeader>
          <CardTitle>NovaStart</CardTitle>
          <CardDescription>前端脚手架就绪：Vite + React 18 + TS + Tailwind + shadcn/ui</CardDescription>
        </CardHeader>
        <CardContent>
          <Button>开始专注</Button>
        </CardContent>
      </Card>
    </div>
  )
}

export default App
