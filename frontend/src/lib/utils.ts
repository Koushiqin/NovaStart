import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

// shadcn/ui 标准 cn()：合并条件类名并去重 Tailwind 冲突
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
