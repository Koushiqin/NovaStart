# 011 深空紫黑视觉刷新（排版与前端优化）

## 1. 背景与目标

参考 `docs/design/` 下的四份样式参考（网站排版、glow 按钮、登录注册玻璃框 + 流星、拟态目标输入框、票据卡片）与 `docs/design/流动背景参考代码.md`（Lightfall WebGL2 背景），把 NovaStart 前端统一成一套「深空紫黑 + 单一霓虹紫光效」的视觉语言。

参考代码与本项目技术栈不一致处，一律按项目技术栈改写：React 18 + Tailwind 3 + shadcn/ui 2.4 CSS 变量 + framer-motion 11，**不新增任何前端依赖**，不引入网络字体。

同时修复一个真实缺陷：`frontend/src/index.css` 的变量值全部是 `oklch(...)`，而 `frontend/tailwind.config.ts` 把颜色映射成 `hsl(var(--x))`，构建产物为 `hsl(oklch(...))`，属于无效值——`bg-background`、`text-foreground`、`bg-card`、`border-border` 等当前实际不生效。本次必须先修好 token 映射，视觉改动才有可信基准。

交付分两批，每批独立可验收：

- 批 1：token / 深色基线 + 顶栏 + 首页 + 登录注册 + 专注页背景。
- 批 2：结算页 + 信箱票据 + 记录页占位 + 星星墙/里程碑换皮。

## 2. 范围与非目标

**范围**

- `frontend/index.html`、`frontend/tailwind.config.ts`、`frontend/src/index.css` 的主题 token 与全局样式。
- `frontend/src/components/ui/`：`button.tsx`（新增 `glow` variant）、`modal.tsx`、`card.tsx`（批 2）、新增 `letter-ticket.tsx`、新增 `meteor-field.tsx`。
- `frontend/src/App.tsx` 顶栏；`AccountSwitcher` 顶栏形态。
- 页面：`HomePage`、`LoginPage`、`RegisterPage`、`FocusPage`、`MailboxPage`、`SettlePage`（批 2 视觉）、`RecordsPage`（仅占位换皮）。
- 组件：`TaskComposer`（仅目标输入区）、`StreakBadge`、`StarWall` 的默认渲染器、`MilestoneBanner`、`SettleSummary`、`StepReflection/StepDeliver/StepMailbox/StepReview`、`CosmicWhisper`、`FocusTimer`、`InboxList/HistoryList/OutboxList`。
- 新增 `frontend/src/features/focus/Lightfall.tsx`（移植参考 WebGL2 组件）。

**非目标**

- 不做明暗主题切换：`html` 常驻 `dark`，只保留一套深色值。
- 不实现参考里无源码的 Galaxy 背景。
- 不生成 / 不下载任何图片资源；首屏与背景全部用 CSS 渐变、conic 与 WebGL 实现。
- 不改后端、数据库、Alembic、API 请求/响应契约。
- 不实现 `RecordsPage` 缺失的业务功能，只统一占位页视觉。
- 不新增测试框架或测试依赖；前端验证仍是 `lint` + `build` + 人工浏览器核对。
- 不改 `StarWallRenderer` 契约、`WallDay` 字段、`state/level` 语义。
- 不改 `StepProps`（`sessionId` + `onDone`）与各阶段组件的对外签名。

## 3. 可测试的验收条件

### 批 1

1. 主题 token 生效：构建后浏览器中 `body` 的 `background-color`、`color` 解析为有效 `oklch(...)`（非空、非 `rgba(0,0,0,0)`），`border-border` 可见。
2. 全站无一处在浅色背景上显示浅色文字：登录、注册、首页、专注页均为深色底。
3. 首页首屏不出现「图片占位」区块；存在发光小标签、`clamp()` 超大标题、唯一一个 `variant="glow"` 主按钮、三个纯文字历史入口。
4. 顶栏 `sticky`、半透明 + 模糊；左侧品牌，右侧导航（登录后出现「信箱 / 记录」）与账号区；移动端不换行溢出。
5. 首页「开始学习」弹窗：只有目标输入区带拟态深灰框 + 旋转 conic 描边；`SplitEditor`、历史记录的年/月/日下拉保持普通深色 input。
6. 登录/注册页为玻璃表单 + CSS 流星背景，无浅色 Card；表单提交、错误提示、跳转行为与改动前一致。
7. Focus 页挂载 Lightfall 背景；`prefers-reduced-motion: reduce` 或 WebGL2 不可用时自动退化为静态径向渐变，计时与结束流程不受影响。
8. `cd frontend; npm run lint` 0 error（允许既有 `button.tsx` fast-refresh warning）；`npm run build` 通过。

### 批 2

1. 信箱的未处理 / 历史 / 发出记录均使用 `LetterTicket`；票据含主票（方向标签 + 日期 + 正文）与存根（日期 + `NO. 0001` 编号），不含座位号、条形码。
2. `<640px` 时票据由左右分栏变为纵向堆叠，无横向滚动；操作按钮仍可点击，409 错误文案与刷新行为不变。
3. 首页「历史收藏信件」弹窗复用同一 `LetterTicket`。
4. 星星墙 30 天网格按服务端 `state/level` 渲染三态，点亮星有光晕；`empty` 仍不绘制；`StarWall` 调用方无需传新参数。
5. 结算页四步与末态的文案、按钮顺序、断点推进不变，仅外观统一为深色面板。
6. `npm run lint` 0 error、`npm run build` 通过；`backend/tests/test_architecture.py` 仍通过（前端改动不应触碰后端棘轮）。

## 4. 现有 owner 和受影响模块

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `frontend/src/index.css` | 主题变量唯一来源 | 重写为深色单套 token，新增 surface/glow/动效类 |
| `frontend/tailwind.config.ts` | token → Tailwind 映射 | 颜色改直接 `var(--x)`，补 `surface`、`glow`、`destructive.foreground` |
| `frontend/index.html` | 文档外壳 | `lang="zh-CN"`、`class="dark"`、标题、内联 SVG favicon |
| `frontend/src/components/ui/button.tsx` | 按钮 API | 新增 `glow` variant，其余不变 |
| `frontend/src/components/ui/modal.tsx` | 弹窗面板 | 深色面板 + 遮罩模糊 + 进出场 |
| `frontend/src/components/ui/card.tsx` | 卡片基础样式 | 圆角/边框/内高光统一，批 2 |
| `frontend/src/components/ui/letter-ticket.tsx` | 新增票据组件 | 信箱三列表 + 首页历史信件共用 |
| `frontend/src/components/ui/meteor-field.tsx` | 新增流星装饰层 | 登录/注册共用，纯装饰 |
| `frontend/src/App.tsx` | 路由外壳 + 顶栏 | 顶栏结构重写，路由表不变 |
| `frontend/src/features/AccountSwitcher.tsx` | 账号区 | 按钮改等宽文字链接形态，逻辑不变 |
| `frontend/src/pages/HomePage.tsx` | 首页 | 首屏/进度区/历史入口重排，数据逻辑不变 |
| `frontend/src/features/task/TaskComposer.tsx` | 目标输入 | 输入区拟态框 + conic 描边，提交逻辑不变 |
| `frontend/src/pages/LoginPage.tsx` / `RegisterPage.tsx` | 认证页 | 玻璃表单 + 流星背景，校验与请求不变 |
| `frontend/src/pages/FocusPage.tsx` | 专注页 | 背景层 + 排版；计时/轮询/结束逻辑逐行保留 |
| `frontend/src/features/focus/Lightfall.tsx` | 新增背景组件 | 移植 WebGL2 源码，仅 Focus 页挂载 |
| `frontend/src/features/focus/FocusTimer.tsx` | 计时展示 | 字号/字距调整，格式化逻辑不变 |
| `frontend/src/features/focus/MilestoneBanner.tsx` | 里程碑提示 | 深色面板 + 光晕，触发条件不变 |
| `frontend/src/features/progress/StreakBadge.tsx` | 连续天数 | 排版换皮，props 不变 |
| `frontend/src/features/progress/StarWall.tsx` | 星星墙 | 只改 `DefaultStarWallRenderer` 样式，契约与容器不变 |
| `frontend/src/pages/MailboxPage.tsx` + `features/mailbox/*List.tsx` | 信箱 | Card 外壳换为分区 + 票据，请求与动作不变 |
| `frontend/src/features/settle/*`、`pages/SettlePage.tsx` | 结算 | 仅外观，阶段推进与文案不变 |
| `frontend/src/pages/RecordsPage.tsx` | 记录占位 | 仅占位视觉统一 |
| `backend/**` | 不动 | 无 |

关键事实的 owner 不变：时间仍由后端 `Clock` 与 `useServerClock` 提供；session / 结算 / 信箱状态仍只来自 PostgreSQL 与现有 API。

## 5. 视觉与组件规范

### 5.1 颜色 token（`index.css`）

`html` 常驻 `class="dark"`，深色值直接写进 `:root`，删除 `.dark` 重复块；Tailwind 映射改为 `var(--x)`，不再包 `hsl()`。

| token | 值 | 用途 |
|---|---|---|
| `--background` | `oklch(0.15 0.025 285)` | 页面底色（深空紫黑） |
| `--surface-1` | `oklch(0.21 0.032 285)` | 卡片 / 面板 |
| `--surface-2` | `oklch(0.26 0.038 285)` | 弹窗 / 输入框 / 票据内层 |
| `--foreground` | `oklch(0.96 0.01 285)` | 主文字 |
| `--muted-foreground` | `oklch(0.70 0.02 285)` | 辅助文字 |
| `--border` | `oklch(0.34 0.03 285 / 0.55)` | 分隔线 / 卡片边框 |
| `--input` | `oklch(0.33 0.03 285 / 0.6)` | 输入框边框 |
| `--primary` | `oklch(0.82 0.13 305)` | 主色（霓虹紫） |
| `--primary-foreground` | `oklch(0.16 0.02 285)` | 主色上的深色文字 |
| `--secondary` | `oklch(0.25 0.03 285)` | 次级按钮底 |
| `--accent` | `oklch(0.29 0.04 290)` | hover 面 |
| `--destructive` | `oklch(0.62 0.19 20)` | 错误 |
| `--destructive-foreground` | `oklch(0.98 0 0)` | 错误按钮文字（补齐缺失映射） |
| `--ring` | `oklch(0.80 0.12 305 / 0.9)` | focus 环 |
| `--glow` | `oklch(0.86 0.13 305)` | 发光主色 |
| `--glow-spread` | `oklch(0.72 0.19 300 / 0.55)` | 扩散光 |
| `--radius` | `0.75rem` | 全局圆角 |

- `--card: var(--surface-1)`、`--card-foreground: var(--foreground)`、`--popover: var(--surface-2)`。
- `--muted` 沿用 surface 附近暗值；`--chart-*`、`--sidebar-*` 保留现值不主动改，避免无谓扩散。
- 星星亮度 token（`--star-level-1/2/3`、`--star-dim`、`--star-broken`）保留，只允许整体提亮，语义不动。

Tailwind `extend.colors` 新增：

```ts
surface: { DEFAULT: "var(--surface-1)", 1: "var(--surface-1)", 2: "var(--surface-2)" },
glow: { DEFAULT: "var(--glow)", spread: "var(--glow-spread)" },
```

`extend.keyframes` / `extend.animation` 新增 `spin-slow`（6s linear infinite）供拟态框描边使用。

### 5.2 排版

- 字体：系统 sans 栈（现 Tailwind 默认）；等宽小标签用 `font-mono`；数字一律 `tabular-nums`。不引入字体文件或 CDN。
- Hero 标题：`font-size: clamp(2.5rem, 7vw, 5.5rem)`、`line-height: 0.95`、`letter-spacing: -0.03em`、`font-semibold`。
- 页面标题：`text-2xl` / `text-3xl`；分组标题：`text-lg`。
- 等宽小标签：`text-[11px] uppercase tracking-[0.3em] text-muted-foreground`。
- 正文：`text-sm` / `text-base`，`leading-relaxed`；辅助 `text-xs`。
- 计时数字：`clamp(3.5rem, 12vw, 5rem)`、`font-mono tabular-nums`。

### 5.3 光效与动效预算

- 每页最多 1 个 glow 元素；首页唯一 glow = Hero 主 CTA；Focus 页唯一 glow = 里程碑后的「结束」按钮（5 分钟前用 outline）。
- `.btn-glow`（定义在 `index.css`，供 `Button variant="glow"` 使用）：移植参考的三层 `box-shadow` + `text-shadow` + `::after` 地面反光，尺寸按 shadcn `lg` 收敛（`padding` 用现有 `px-8`，圆角 `rounded-xl`），`transition: 300ms`。
- 拟态输入描边：`conic-gradient(from 45deg, transparent 75%, var(--glow), transparent)` 覆盖层 + `animate-spin-slow` + `motion-reduce:animate-none`。
- Modal：`animate-in fade-in zoom-in-95 duration-200`（沿用已装的 `tailwindcss-animate`），不新增 framer-motion 用法。
- 流星：登录/注册各 1 层 `MeteorField`（6 颗），时长/延迟沿用参考值（1s / 3s / 2.75s / 1.6s / 2.2s / 3.2s）；`prefers-reduced-motion` 下整层 `display: none`。
- framer-motion 仅保留 `SettleSummary` 现有的星星缩放动画；不扩展。
- Lightfall 仅 Focus 页挂载，离开即卸载。

### 5.4 组件规格

**顶栏（`App.tsx`）**

- `sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-md`。
- 内层 `mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6`。
- 左：`NovaStart` 文字（`Link` 到 `/`）+ 发光小圆点（`bg-glow shadow-[0_0_12px_var(--glow)]`）。
- 右：登录后「信箱 / 记录」等宽文字链接（`/mailbox`、`/records`，`hidden sm:flex`）+ `AccountSwitcher`；未登录只显示登录/注册文字链接。

**首页首屏（`HomePage` Hero 区）**

- `min-h-[78vh]` 居中；背景为 `.space-glow`（index.css：两层 radial-gradient 紫色光斑 + 底部 vignette），不使用图片。
- 结构：等宽小标签 `DAILY PRACTICE · 5 MIN` → 超大标题「每天五分钟」→ 次行「主动学习一点点」（同字号阶、`text-muted-foreground`）→ 一行副文案 → `Button variant="glow" size="lg"`（文案与禁用逻辑不变）→ 提示文案。
- 删除「图片占位」块。
- 历史三入口改为居中纯文字按钮：`font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground hover:text-foreground`，点击行为不变。

**首页进度区**

- 去掉外层 `Card`：`border-t border-border/60 pt-10` 的分区。
- `StreakBadge`：等宽标签 `CURRENT STREAK` + `text-5xl font-semibold tabular-nums` 数字 + 右侧 `天连续 · 最长 X 天`（props 不变）。
- `DefaultStarWallRenderer`：`grid-cols-10`，间距 `gap-2.5`，星星 `h-5 w-5 sm:h-6 sm:w-6`；点亮项加 `drop-shadow` 光晕；`empty` 仍占位不绘制。

**Modal**

- 遮罩 `bg-background/70 backdrop-blur-sm`；面板 `rounded-2xl border border-border/70 bg-surface-2 p-6 shadow-[0_24px_80px_-24px_rgba(0,0,0,0.9)]`。
- 标题上方加静态等宽 eyebrow `NOVASTART`，标题保持 `text-lg font-semibold`；`children` 与 `onClose`/Esc 逻辑不变。

**拟态目标输入框（仅 `TaskComposer` 输入区）**

- 外层：`relative overflow-hidden rounded-3xl bg-surface p-1.5 shadow-[0_8px_24px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.08)]`。
- 描边层：`pointer-events-none absolute -inset-12 bg-[conic-gradient(from_45deg,transparent_75%,var(--glow)_88%,transparent)] animate-spin-slow motion-reduce:animate-none`。
- 内层：`relative rounded-[1.25rem] bg-surface-2 p-3`，label 用等宽小标签，input 为深灰内嵌（无外边框，focus 只加 `ring-1 ring-ring`），保留 `maxLength`、计数、禁用态。
- 示例 chips 改胶囊描边；「分析」按钮沿用 `default`，弹窗主操作「开始学习」沿用 `default`，二者都不使用 glow。

**登录 / 注册**

- 页面：深色底 + `MeteorField` 装饰层（`pointer-events-none fixed inset-0 overflow-hidden`）。
- 表单：`.glass-form`（参考渐变 + 1px 白色低透明边框 + 青色外发光 + `backdrop-blur`），`max-w-sm`、`rounded-2xl`、`p-8`。
- 标题两级：等宽 eyebrow（`SIGN IN` / `SIGN UP`）+ 拉丁描边主标题 `NOVASTART`（`-webkit-text-stroke`，仅用于拉丁字，避免中文描边影响可读性）；下方一行中文说明。
- 输入框：深色内嵌 + 1px 边框，focus 变亮；提交按钮用紫→青渐变 + hover 扫光（参考 `sh02`，纯 CSS，`motion-reduce` 关闭）。
- 校验、错误文案、`login/register` 请求与跳转逻辑逐行保留。

**Focus 页**

- 容器：`relative isolate min-h-screen overflow-hidden`；静态层 `.focus-backdrop`（顶部紫色光晕 + 底部 vignette）常驻，保证降级可见；`Lightfall` 绝对定位 `inset-0 -z-10`。
- Lightfall 参数：`colors=['#c4b5fd','#f0abfc','#a78bfa']`、`backgroundColor='#08060f'`、`speed=0.25`、`streakCount=2`、`streakWidth=0.7`、`glow=0.9`、`density=0.55`、`twinkle=0.25`、`zoom=3`、`bloom=0.35`、`intro=true`、`dpr={Math.min(devicePixelRatio, 1.5)}`、`mouseInteraction=true`。
- 降级：`prefers-reduced-motion: reduce` 时不挂载 Lightfall；WebGL2 不可用时组件自身不渲染 canvas（源码已返回），静态层兜底。
- 排版：等宽小标签「本次专注」+ 任务首步、计时数字（5.2 字号阶）、提示文案；按钮区宽度不变。
- 里程碑：保持 `status==="completed" && ended_at===null` 判定；`.focus-backdrop--milestone` 提高光晕；「结束」按钮在里程碑时切到 `variant="glow"`。
- 清理：保留参考源码的 `cancelAnimationFrame`、`removeEventListener`、`deleteTexture`、`deleteProgram`；不得只卸载组件而遗漏 GPU 释放。

**票据（`letter-ticket.tsx`）**

```ts
interface LetterTicketProps {
  id: number
  dateISO: string
  content: string
  counterpart: string | null
  direction: "in" | "out"
  status?: string
  actions?: ReactNode
}
```

- 主票：等宽标签（`FROM`/`TO` + 对应名字 + 日期）+ 正文；`actions` 放主票底部。
- 存根：`NO. {id 补零 4 位}` + 日期；`t-perforation` 用 `border-dashed` + 两侧凹口（`before/after` 圆形，填 `--background`）。
- 桌面 `sm:flex-row`（存根 `sm:w-32`），移动端纵向堆叠；整体 `max-w-sm`、`bg-surface-2`、`rounded-2xl`、细边框。
- **剪掉**座位号、条形码与假的活动信息；`status`（专注时投递 / 已投递 / 未送达）显示在存根或主票右上角。

**记录页占位**

- 仅把浅色居中标题改为：等宽 eyebrow `RECORDS` + 标题 + 一句「记录页建设中」；不实现任何查询功能。

### 5.5 实现步骤 · 批 1

1. `index.html`：`lang="zh-CN"`、`<html class="dark">`、标题 `NovaStart · 每天五分钟`、favicon 换为内联 SVG 星星 data URI（不新增图片文件）。
2. `index.css`：按 5.1 重写 `:root`（删除 `.dark` 块），新增 `surface`/`glow` token；新增 `.space-glow`、`.focus-backdrop`、`.focus-backdrop--milestone`、`.btn-glow`、`.glass-form`、`.meteor-field` 与对应 keyframes；保留星星 token。
3. `tailwind.config.ts`：所有颜色改 `var(--x)`；补 `surface`、`glow`、`destructive.foreground`；新增 `spin-slow` 动画。
4. `button.tsx`：新增 `variant: { glow: "btn-glow ..." }`，不改 base 与其它 variant。
5. `modal.tsx`：按 5.4 Modal 调整面板/遮罩/标题，保留 Esc 与关闭逻辑。
6. `App.tsx`：重写顶栏（品牌 + 登录后导航 + `AccountSwitcher`），路由表不变。
7. `AccountSwitcher.tsx`：按钮改等宽文字链接形态，登录/登出/切账号逻辑不变。
8. `HomePage.tsx`：Hero 重排（删图片占位）、glow CTA、文字入口、进度区去 Card；历史信件弹窗本批先用现有列表样式，批 2 换票据。
9. `TaskComposer.tsx`：只给目标输入区套拟态框与 conic 描边；其余结构与校验不变。
10. `LoginPage.tsx` / `RegisterPage.tsx`：玻璃表单 + `MeteorField`；逻辑不变。
11. 新增 `meteor-field.tsx`：6 颗 `.star` span，纯装饰、`aria-hidden`。
12. 新增 `features/focus/Lightfall.tsx`：移植 `docs/design/流动背景参考代码.md` 的完整 WebGL2 实现，去掉 `'use client'`，保留 props 与清理逻辑。
13. `FocusPage.tsx` / `FocusTimer.tsx`：接入静态背景 + Lightfall，排版与里程碑光晕；计时/轮询/结束代码不动。
14. 跑 `npm run lint` + `npm run build`，人工截图核对批 1 清单。

### 5.6 实现步骤 · 批 2

1. `card.tsx`：统一深色面板基础样式（圆角、边框、内高光），全局生效。
2. 新增 `letter-ticket.tsx`；`InboxList` / `HistoryList` / `OutboxList` 改为票据（props 签名不变），`MailboxPage` 的 Card 外壳改为等宽小标签分区。
3. `HomePage` 历史收藏信件弹窗改用 `LetterTicket`。
4. `StreakBadge` 与 `DefaultStarWallRenderer` 按 5.4 换皮，契约不动。
5. `MilestoneBanner`、`SettleSummary`、`StepReflection`、`StepDeliver`、`StepMailbox`、`StepReview`、`CosmicWhisper` 统一深色面板与标签排版，文案与阶段推进不变。
6. `RecordsPage` 仅占位换皮。
7. 跑 `npm run lint` + `npm run build` + `backend/tests/test_architecture.py`，人工截图核对批 2 清单。

## 6. 接口、数据及兼容性变化

- 后端 API、数据库、Alembic：**无变化**。
- `StarWall` 契约（`StarWallRendererProps`、`WallDay`、`state/level`）不变；`HomePage` 调用不变。
- `StepProps` 与结算阶段组件签名不变，仅替换内部样式。
- `Button` 新增可选 `variant="glow"`，向后兼容；`Modal` props 不变。
- 新增前端组件 `LetterTicket`、`MeteorField`、`Lightfall`，均为新增文件而非改动既有契约；新增理由：票据被 4 处复用、流星被 2 处复用、Lightfall 是独立 WebGL 单元。
- 全局 token 映射修正会一次性改变所有页面的底色/文字色：这是预期效果，批 1 结束时结算/信箱虽未重排也会自动变深色，不得回退映射。

## 7. 测试场景与验证命令

```powershell
# 前端（每批结束）
cd frontend; npm run lint; npm run build

# 后端棘轮（确认前端改动未波及后端，无需数据库）
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py
```

人工核对（浏览器打开 `npm run dev`）：

- token：DevTools 检查 `body` 背景/文字为有效 `oklch`，`Card`、`Modal`、`border` 均可见。
- 批 1：首页首屏无图片占位、唯一 glow 按钮；弹窗输入框有旋转描边且 `SplitEditor` 无描边；登录/注册玻璃框与流星；Focus 背景流动、切到「减少动态效果」后为静态渐变；移动端顶栏不溢出。
- 批 2：信箱三类票据、移动端堆叠、收藏/放弃/删除行为与 409 文案；星星墙三态；结算四步与末态顺序。

截图仅用于本地核对，不入库。

## 8. 执行结果、未验证项和遗留问题

（回填于 2026-11-08，分支 `美化排版和前端优化`；批 1 = Task 1–12，commits `5b3ba03..33416a1`；批 2 = Task 13–20，代码 commits `33416a1..e2aaef0`，Task 20 文档提交另计）

### 已运行通过（有命令输出）

| 检查 | 命令 | 结果 |
|---|---|---|
| 前端 lint | `cd frontend; npm run lint` | 0 error，仅既有 `button.tsx` fast-refresh warning |
| 前端 build | `cd frontend; npm run build` | 通过，2543 modules，2.74s |
| 后端棘轮 | `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py` | 77 passed |
| token 生效 | DevTools（`npm run dev` :5174） | `body` background-color = `oklch(0.15 0.025 285)`（非透明）；构建 CSS 中 `hsl(var(` 出现 0 次 |
| 产物静态核验 | 构建产物 grep | CSS 含 `space-glow`/`btn-glow`/`glass-form`/`glass-submit`/`meteor-field`/`focus-backdrop`/`focus-backdrop--milestone` 与 `spin-slow`/`sh02`/`meteor` keyframes；JS 含 WebGL2 着色器源码与 `WEBGL_lose_context`（Lightfall 已打包） |
| 浏览器核对（公开页） | :5174 | 首页（eyebrow / 超大标题 / 唯一 glow CTA / 无图片占位）、`/login`（玻璃表单 + NOVASTART 描边标题 + 流星）、顶栏（发光圆点 + 登录/注册文字链接）均 PASS，无 console error |

### 批 1 验收条件逐条状态

1. token 生效 — **已运行验证**（见上表）。
2. 全站深色底 — 首页/登录已验证；`/focus`、结算、信箱未运行时核对（需登录态 + 活动会话）。
3. 首页首屏 — **已运行验证** PASS。
4. 顶栏 sticky/品牌/导航 — 公开页 PASS；登录后「信箱/记录」与 375px 不溢出未运行时核对。
5. 「开始学习」弹窗拟态描边 / `SplitEditor` 下拉无描边 — 未运行时核对。
6. 登录/注册玻璃 + 流星 — 视觉 PASS；提交成功/失败往返未运行时核对。
7. Focus 页 Lightfall + 降级 — **未运行时验证**。浏览器自动化连续 3 次因页面焦点丢失（"Type target page lost focus"）失败，未能到达 `/focus`。代码级已确认：`!reducedMotion` 时整层不挂载 Lightfall（`matchMedia` effect 只驱动渲染开关，不接触计时/轮询/结束）；WebGL2 不可用或着色器链接失败时组件返回 `undefined`、不渲染 canvas；卸载执行 `cancelAnimationFrame`/`removeEventListener`/`deleteTexture`/`deleteProgram` + `loseContext`。
8. lint/build — **已运行验证** PASS。

### 批 2 已运行通过（有命令/产物输出）

| 检查 | 命令 / 方式 | 结果 |
|---|---|---|
| 前端 lint | `cd frontend; npm run lint` | 0 error，仅既有 `button.tsx` fast-refresh warning |
| 前端 build | `cd frontend; npm run build` | 通过，2544 modules，2.46s |
| 后端棘轮 | `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py` | 77 passed |
| 产物静态核验 | 构建产物 grep | JS 含 `FROM`/`TO`/`NO. `（票据）、`RECORDS`/`记录页建设中`（记录页）、`CURRENT STREAK`/`专注时投递`/`已投递`/`未送达`；CSS 含 `border-dashed`、`drop-shadow`（点亮星光晕）、`tabular-nums`、`bg-surface-2`、`max-w-sm`、640px `sm` 断点 |
| 浏览器核对（记录页） | `:5174` 登录演示账号 `e2e011` 后打开 `/records` | PASS：eyebrow `RECORDS` + 标题「记录」+「记录页建设中」，深色底，无 console error；顶栏登录态出现「切换账号 / 登出」 |
| 浏览器核对（信箱空态） | 同上打开 `/mailbox` | 空态文案正常、深色底、无横向滚动、无 console error（`e2e011` 无信件，票据本体未渲染） |

### 批 2 验收条件逐条状态

1. 信箱三类票据 — 代码级确认 `InboxList`/`HistoryList`/`OutboxList` 均渲染 `LetterTicket`（主票 FROM/TO + 日期 + 正文，存根 `NO. ####`，虚线分隔与两侧凹口）；运行时 `e2e011` 信箱为空态，票据未实际渲染 → **未运行时核对**。
2. `<640px` 纵向堆叠 / 无横向滚动 / 409 文案 — 代码级：票据默认 `flex-col`，`sm:` 断点切 `flex-row`；运行时信箱默认视口无横向滚动；票据堆叠与 409 收藏流程 → **未运行时核对**。
3. 首页历史信件弹窗复用票据 — 代码级：Task 16 已替换为 `LetterTicket direction="in"`；账号无收藏信件 → **未运行时核对**。
4. 星星墙三态 + 点亮光晕 — 代码级：`DefaultStarWallRenderer` 间距/尺寸/`state==="lit"` 的 `drop-shadow`/`empty` 仍占位不绘制；运行 → **未运行时核对**。
5. 结算四步与末态文案/按钮顺序 — 代码级：Task 18 diff 为 20 insertions / 2 deletions，全部展示层，`onDone` 时机与请求逻辑未动；运行（需活动会话）→ **未运行时核对**。
6. lint / build / 架构棘轮 — **已运行验证** PASS（见上表）。

### 遗留问题

- 未新增前端依赖、未生成/下载任何图片；后端零改动。
- `:5174` 为上一会话遗留的 dev server 实例（本次沿用，`:5173` 空闲）。
- 上述「未运行时核对」项需人工在浏览器补做（登录后：`/focus` 背景与 reduce/WebGL 降级、结算/信箱可读性、弹窗描边、375px 顶栏与票据）。
- 批 2 运行时核对受浏览器自动化限制（登录表单填入后提交偶发不跳转 / 页面焦点丢失），信箱票据、星星墙三态、结算四步仍需人工在浏览器补做；记录页与信箱空态已实际打开核对。


---

> 结构性变更五问：
> 1. **修改哪一层？** 仅前端展示层（`index.css` token、Tailwind 映射、`pages/features/components/ui`），后端与数据库零改动。
> 2. **当前 owner 在哪里？** 颜色/字体/圆角 = `index.css` + `tailwind.config.ts`；星星亮度 = `--star-*`；页面数据 = 现有 API，`clock.py` 与 `useServerClock` 仍是时间唯一来源。
> 3. **是否引入重复状态或平行写入？** 否。新增组件只接收展示数据，无任何 localStorage/前端缓存或第二写入路径。
> 4. **是否影响接口和其他模块？** 否。API 契约、`StarWall` 契约、结算组件签名均不变；`Button`/`Modal` 变更向后兼容。
> 5. **哪些现有检查需要继续通过？** `backend/tests/test_architecture.py`（棘轮）、`npm run lint`、`npm run build`；不新增测试依赖、不放宽任何检查。
