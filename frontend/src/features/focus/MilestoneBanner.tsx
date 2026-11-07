// 5 分钟里程碑的一次性轻提示：只提示，不跳转、不停表；由页面在 completed 且未结束时挂载一次
export default function MilestoneBanner() {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-500 rounded-lg border bg-card px-4 py-3 text-center text-sm shadow-sm">
      已经 5 分钟，随时可以结束，也可以继续。
    </div>
  )
}
