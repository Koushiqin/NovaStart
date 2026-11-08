import { StarIcon } from "@/features/progress/StarWall"

// 5 分钟里程碑的一次性轻提示：只提示，不跳转、不停表；由页面在 completed 且未结束时挂载一次。
// 小星星与 FocusPage 背景变亮同一次触发（都随 milestone 挂载播放一次，不做循环动画）。
export default function MilestoneBanner() {
  return (
    <div className="flex animate-in fade-in slide-in-from-bottom-2 items-center justify-center gap-2 rounded-2xl border border-border/70 bg-surface-2 px-4 py-3 text-center text-sm shadow-[0_0_24px_-10px_var(--glow)] duration-500">
      <StarIcon
        variant="lit"
        level={1}
        glow
        className="h-4 w-4 animate-in fade-in zoom-in duration-500"
      />
      <span>已经 5 分钟，随时可以结束，也可以继续。</span>
    </div>
  )
}
