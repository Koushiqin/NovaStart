import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

export interface GalaxyProps {
  /** 星点密度倍数（1 = 基准 ~260 颗） */
  density?: number
  /** 星点光晕强度 0–1 */
  glowIntensity?: number
  /** 中心星云辉光强度 0–1 */
  flareIntensity?: number
  /** 自转速度倍数 */
  starSpeed?: number
  /** 鼠标半径内推开星点并缓慢回落 */
  mouseRepulsion?: boolean
  /** 点击后短暂加速自转 + 径向脉冲 */
  clickWarp?: boolean
  className?: string
}

interface Star {
  radius: number
  angle: number
  size: number
  depth: number
  color: 0 | 1
  phase: number
  offsetX: number
  offsetY: number
}

function makeSprite(rgb: string): HTMLCanvasElement {
  const size = 64
  const canvas = document.createElement("canvas")
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext("2d")
  if (!ctx) return canvas
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  gradient.addColorStop(0, `rgba(${rgb},1)`)
  gradient.addColorStop(0.18, `rgba(${rgb},0.72)`)
  gradient.addColorStop(0.45, `rgba(${rgb},0.15)`)
  gradient.addColorStop(1, `rgba(${rgb},0)`)
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)
  return canvas
}

function buildStars(count: number): Star[] {
  const arms = 3
  const stars: Star[] = []
  for (let i = 0; i < count; i += 1) {
    // pow 使星点向中心聚集，形成螺旋臂
    const radius = Math.pow(Math.random(), 1.45)
    const arm = i % arms
    const jitter = (Math.random() - 0.5) * 0.6
    stars.push({
      radius,
      angle: radius * 5.4 + arm * ((Math.PI * 2) / arms) + jitter,
      size: 0.35 + Math.random() * 0.65,
      depth: 0.35 + Math.random() * 0.65,
      color: Math.random() < 0.22 ? 1 : 0,
      phase: Math.random() * Math.PI * 2,
      offsetX: 0,
      offsetY: 0,
    })
  }
  return stars
}

/**
 * 首页深空星场：Canvas2D + 离屏光晕精灵，螺旋臂缓慢自转。
 * 纯展示组件：不读写 store、不发请求；reduce 时只画一帧；卸载释放 rAF 与监听。
 */
export default function Galaxy({
  density = 1,
  glowIntensity = 0.3,
  flareIntensity = 1,
  starSpeed = 0.5,
  mouseRepulsion = false,
  clickWarp = false,
  className,
}: GalaxyProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const reducedMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const whiteSprite = makeSprite("245,244,248")
    const lilacSprite = makeSprite("217,211,228")
    const flareSprite = makeSprite("63,36,118")

    const stars = buildStars(Math.round(260 * density))
    const pointer = { x: -9999, y: -9999, active: false }
    const repulsionRadius = 150

    let width = 0
    let height = 0
    let dpr = 1
    let rotation = 0
    let warp = 0
    let lastFrame = performance.now()
    let rafId = 0

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      dpr = Math.min(window.devicePixelRatio || 1, 1.5)
      width = Math.max(1, rect.width)
      height = Math.max(1, rect.height)
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const drawFrame = (now: number) => {
      const delta = Math.min(now - lastFrame, 48)
      lastFrame = now
      if (warp > 0) warp = Math.max(0, warp - delta / 900)
      rotation += delta * starSpeed * 0.00022 * (1 + warp * 6)

      const scale = 1 + warp * 0.05
      const centerX = width * 0.66
      const centerY = height * 0.44
      const maxRadius = Math.min(width, height) * 0.42

      ctx.clearRect(0, 0, width, height)
      ctx.globalCompositeOperation = "lighter"

      // 中心星云辉光（静态渐变精灵，避免每帧新建渐变）
      if (flareIntensity > 0) {
        const flareSize = maxRadius * 2.2
        ctx.globalAlpha = 0.16 * flareIntensity * (1 + warp * 0.5)
        ctx.drawImage(
          flareSprite,
          centerX - flareSize / 2,
          centerY - flareSize / 2,
          flareSize,
          flareSize
        )
      }

      for (let i = 0; i < stars.length; i += 1) {
        const star = stars[i]
        const angle = star.angle + rotation
        const radius = star.radius * maxRadius * scale
        const x = centerX + Math.cos(angle) * radius * 1.35
        const y = centerY + Math.sin(angle) * radius * 0.82

        let targetX = 0
        let targetY = 0
        if (mouseRepulsion && pointer.active) {
          const dx = x - pointer.x
          const dy = y - pointer.y
          const distance = Math.hypot(dx, dy)
          if (distance < repulsionRadius && distance > 0.1) {
            const force = (1 - distance / repulsionRadius) * 26
            targetX = (dx / distance) * force
            targetY = (dy / distance) * force
          }
        }
        star.offsetX += (targetX - star.offsetX) * 0.09
        star.offsetY += (targetY - star.offsetY) * 0.09

        const screenX = x + star.offsetX
        const screenY = y + star.offsetY
        const twinkle = 0.72 + 0.28 * Math.sin(now * 0.0012 + star.phase)
        const sprite = star.color === 0 ? whiteSprite : lilacSprite
        const spriteSize = (9 + star.size * 13) * (1 + glowIntensity * 0.8)

        ctx.globalAlpha = Math.min(1, (0.18 + star.depth * 0.6) * twinkle)
        ctx.drawImage(
          sprite,
          screenX - spriteSize / 2,
          screenY - spriteSize / 2,
          spriteSize,
          spriteSize
        )
      }

      ctx.globalAlpha = 1
      ctx.globalCompositeOperation = "source-over"
    }

    const tick = (now: number) => {
      drawFrame(now)
      rafId = window.requestAnimationFrame(tick)
    }

    const onPointerMove = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect()
      pointer.x = event.clientX - rect.left
      pointer.y = event.clientY - rect.top
      pointer.active = pointer.y >= 0 && pointer.y <= rect.height
    }

    const onPointerLeave = () => {
      pointer.active = false
    }

    const onPointerDown = () => {
      if (clickWarp) warp = 1
    }

    resize()
    const observer =
      typeof ResizeObserver === "function" ? new ResizeObserver(resize) : null
    observer?.observe(canvas)

    if (reducedMotion) {
      drawFrame(performance.now())
    } else {
      rafId = window.requestAnimationFrame(tick)
      window.addEventListener("pointermove", onPointerMove)
      window.addEventListener("pointerdown", onPointerDown)
      window.addEventListener("pointerleave", onPointerLeave)
    }

    return () => {
      window.cancelAnimationFrame(rafId)
      observer?.disconnect()
      window.removeEventListener("pointermove", onPointerMove)
      window.removeEventListener("pointerdown", onPointerDown)
      window.removeEventListener("pointerleave", onPointerLeave)
    }
  }, [density, glowIntensity, flareIntensity, starSpeed, mouseRepulsion, clickWarp])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={cn("pointer-events-none h-full w-full", className)}
    />
  )
}
