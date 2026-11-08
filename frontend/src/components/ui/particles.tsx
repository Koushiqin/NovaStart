import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

export interface ParticlesProps {
  /** 粒子颜色（CSS 颜色字符串） */
  particleColors?: string[]
  particleCount?: number
  /** 深度分布倍数（越大视差层越丰富） */
  particleSpread?: number
  /** 漂移速度倍数 */
  speed?: number
  /** 粒子基础尺寸（100 = 基准） */
  particleBaseSize?: number
  /** 光晕强度 0–1 */
  glow?: number
  /** 闪烁幅度 0–1 */
  twinkle?: number
  moveParticlesOnHover?: boolean
  hoverEffect?: "parallax" | "none"
  className?: string
}

interface Particle {
  x: number
  y: number
  depth: number
  size: number
  phase: number
  velocityX: number
  velocityY: number
}

function parseColor(color: string): [string, string, string] {
  const hex = color.trim().replace("#", "")
  if (hex.length === 3) {
    return [
      parseInt(hex[0] + hex[0], 16).toString(),
      parseInt(hex[1] + hex[1], 16).toString(),
      parseInt(hex[2] + hex[2], 16).toString(),
    ]
  }
  if (hex.length === 6) {
    return [
      parseInt(hex.slice(0, 2), 16).toString(),
      parseInt(hex.slice(2, 4), 16).toString(),
      parseInt(hex.slice(4, 6), 16).toString(),
    ]
  }
  return ["255", "255", "255"]
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
  gradient.addColorStop(0.16, `rgba(${rgb},0.85)`)
  gradient.addColorStop(0.4, `rgba(${rgb},0.22)`)
  gradient.addColorStop(1, `rgba(${rgb},0)`)
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)
  return canvas
}

/**
 * 专注页粒子背景：Canvas2D + 离屏光晕精灵。
 * 纯展示组件；reduce 时只画一帧；卸载释放 rAF、监听与观察器。
 */
export default function Particles({
  particleColors = ["#ffffff"],
  particleCount = 200,
  particleSpread = 10,
  speed = 0.1,
  particleBaseSize = 100,
  glow = 0.5,
  twinkle = 0.3,
  moveParticlesOnHover = false,
  hoverEffect = "parallax",
  className,
}: ParticlesProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const reducedMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const palette = (particleColors.length > 0 ? particleColors : ["#ffffff"]).slice(0, 4)
    const sprites = palette.map((color) => makeSprite(parseColor(color).join(",")))

    let width = 0
    let height = 0
    let dpr = 1
    const particles: Particle[] = []
    const pointer = { x: 0, y: 0, active: false }
    let rafId = 0
    let lastFrame = performance.now()

    const spawn = (particle: Particle) => {
      particle.x = Math.random() * width
      particle.y = Math.random() * height
      particle.depth = 0.2 + Math.random() * 0.8
      particle.size = 0.5 + Math.random()
      particle.phase = Math.random() * Math.PI * 2
      const drift = speed * 40
      particle.velocityX = (Math.random() - 0.5) * drift
      particle.velocityY = (Math.random() - 0.5) * drift
    }

    for (let i = 0; i < particleCount; i += 1) {
      const particle: Particle = {
        x: 0,
        y: 0,
        depth: 0,
        size: 0,
        phase: 0,
        velocityX: 0,
        velocityY: 0,
      }
      spawn(particle)
      particles.push(particle)
    }

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      const previousWidth = width
      const previousHeight = height
      const nextWidth = Math.max(1, rect.width)
      const nextHeight = Math.max(1, rect.height)
      dpr = Math.min(window.devicePixelRatio || 1, 1.5)
      width = nextWidth
      height = nextHeight
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      // 首次拿到尺寸后才分布粒子；之后尺寸变化只把越界粒子拉回可见区
      if (previousWidth === 0 || previousHeight === 0) {
        particles.forEach(spawn)
      } else {
        particles.forEach((particle) => {
          if (particle.x > width || particle.y > height) spawn(particle)
        })
      }
    }

    const drawFrame = (now: number) => {
      const delta = Math.min(now - lastFrame, 48)
      lastFrame = now
      ctx.clearRect(0, 0, width, height)
      ctx.globalCompositeOperation = "lighter"

      const parallaxScale = hoverEffect === "parallax" ? 26 * (particleSpread / 10) : 0
      const shiftX = pointer.active ? pointer.x * parallaxScale : 0
      const shiftY = pointer.active ? pointer.y * parallaxScale : 0

      for (let i = 0; i < particles.length; i += 1) {
        const particle = particles[i]
        if (!reducedMotion) {
          particle.x += particle.velocityX * (delta / 1000)
          particle.y += particle.velocityY * (delta / 1000)
          if (particle.x < -8) particle.x = width + 8
          if (particle.x > width + 8) particle.x = -8
          if (particle.y < -8) particle.y = height + 8
          if (particle.y > height + 8) particle.y = -8
        }

        const baseSize = (particleBaseSize / 100) * (1.2 + particle.depth * 2.2) * particle.size
        const spriteSize = baseSize * (4 + glow * 6)
        const flicker = reducedMotion
          ? 1
          : 1 - twinkle * (0.5 + 0.5 * Math.sin(now * 0.0016 + particle.phase))
        const screenX = particle.x - shiftX * particle.depth
        const screenY = particle.y - shiftY * particle.depth
        const sprite = sprites[i % sprites.length]

        ctx.globalAlpha = Math.min(1, (0.35 + particle.depth * 0.55) * flicker)
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
      if (!moveParticlesOnHover) return
      const rect = canvas.getBoundingClientRect()
      pointer.x = ((event.clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1
      pointer.y = ((event.clientY - rect.top) / Math.max(1, rect.height)) * 2 - 1
      pointer.active = true
    }

    const onPointerLeave = () => {
      pointer.active = false
    }

    resize()
    const observer =
      typeof ResizeObserver === "function" ? new ResizeObserver(resize) : null
    observer?.observe(canvas)

    if (reducedMotion) {
      drawFrame(performance.now())
    } else {
      rafId = window.requestAnimationFrame(tick)
      if (moveParticlesOnHover) {
        window.addEventListener("pointermove", onPointerMove)
        window.addEventListener("pointerleave", onPointerLeave)
      }
    }

    return () => {
      window.cancelAnimationFrame(rafId)
      observer?.disconnect()
      window.removeEventListener("pointermove", onPointerMove)
      window.removeEventListener("pointerleave", onPointerLeave)
    }
  }, [
    particleColors,
    particleCount,
    particleSpread,
    speed,
    particleBaseSize,
    glow,
    twinkle,
    moveParticlesOnHover,
    hoverEffect,
  ])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={cn("pointer-events-none h-full w-full", className)}
    />
  )
}
