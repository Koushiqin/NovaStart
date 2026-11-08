import { motion, useReducedMotion, type Variants } from "framer-motion"
import { cn } from "@/lib/utils"

export type TextEffectPreset = "fade" | "blur" | "slide"

export interface TextEffectProps {
  children: string
  /** 逐字或逐词，默认逐字 */
  per?: "char" | "word"
  preset?: TextEffectPreset
  /** 整段开始前的延迟（秒） */
  delay?: number
  /** 相邻元素之间的间隔（秒） */
  staggerDuration?: number
  className?: string
}

const PRESETS: Record<TextEffectPreset, Variants> = {
  fade: { hidden: { opacity: 0 }, visible: { opacity: 1 } },
  blur: {
    hidden: { opacity: 0, filter: "blur(8px)" },
    visible: { opacity: 1, filter: "blur(0px)" },
  },
  slide: {
    hidden: { opacity: 0, y: "0.4em" },
    visible: { opacity: 1, y: 0 },
  },
}

/**
 * 逐字/逐词入场：按词分组保证换行仍在词边界，词内逐字 stagger。
 * 无障碍：视觉层 aria-hidden，真实文本以 sr-only 提供一次；
 * prefers-reduced-motion 时直接渲染纯文本（不挂载 motion）。
 */
export default function TextEffect({
  children,
  per = "char",
  preset = "fade",
  delay = 0,
  staggerDuration,
  className,
}: TextEffectProps) {
  const reducedMotion = useReducedMotion()

  if (reducedMotion) {
    return <span className={className}>{children}</span>
  }

  const words = children.split(" ")
  const stagger = staggerDuration ?? (per === "char" ? 0.035 : 0.06)
  const item = PRESETS[preset]

  return (
    <motion.span
      className={cn("inline", className)}
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: stagger, delayChildren: delay } },
      }}
    >
      <span className="sr-only">{children}</span>
      <span aria-hidden="true">
        {words.map((word, wordIndex) => (
          <span key={`${wordIndex}-${word}`}>
            <span className="inline-block whitespace-nowrap">
              {per === "word" ? (
                <motion.span className="inline-block" variants={item}>
                  {word}
                </motion.span>
              ) : (
                Array.from(word).map((char, charIndex) => (
                  <motion.span key={charIndex} className="inline-block" variants={item}>
                    {char}
                  </motion.span>
                ))
              )}
            </span>
            {wordIndex < words.length - 1 && " "}
          </span>
        ))}
      </span>
    </motion.span>
  )
}
