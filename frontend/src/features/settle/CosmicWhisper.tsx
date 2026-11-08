import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

// 结算末态（A14 定稿文案）：四步走完才出现；「再学一场」回首页并直接打开输入新目标的流程
export default function CosmicWhisper() {
  const navigate = useNavigate()

  return (
    <Card>
      <CardContent className="space-y-5 p-6 text-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
          SETTLED
        </p>
        <p className="text-xl font-semibold leading-relaxed">
          5 分钟的星星，
          <br />
          是你自己点亮的。
        </p>
        <div className="space-y-2">
          <Button
            className="w-full"
            onClick={() => navigate("/", { state: { startNewTask: true } })}
          >
            再学一场
          </Button>
          <Button className="w-full" variant="outline" onClick={() => navigate("/")}>
            回到首页
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
