# 011 深空紫黑视觉刷新 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans（本项目无 subagent-driven 流程）按任务顺序实现。步骤使用 checkbox（`- [ ]`）追踪。

**Goal:** 把 NovaStart 前端统一为「深空紫黑 + 单一霓虹紫光效」视觉语言，先修复失效的主题 token 映射，再分两批改皮，全程不动业务逻辑。

**Architecture:** 纯展示层改动：CSS 变量 token → Tailwind 映射 → ui 组件 variant → 页面排版。新增 3 个纯展示组件（`MeteorField`、`Lightfall`、`LetterTicket`），均为新增文件。不引入新依赖、不改 API 契约、不改任何状态/请求/轮询/导航逻辑。

**Tech Stack:** React 18 + Tailwind 3 + shadcn/ui 2.4 CSS 变量 + tailwindcss-animate + WebGL2（Lightfall，无依赖）。

**Spec:** `docs/specs/011-visual-refresh.md`（token 值、组件规格、验收条件以此为准，计划引用其章节号，不复述全文）

## Global Constraints

- **不修改业务功能**：每个「Modify」文件只允许改 JSX 结构（包裹层）与 className；事件处理、请求、轮询、条件渲染、文案、props 签名逐行保留。任何任务若发现必须改逻辑才能实现，停下来报告。
- 不新增任何前端依赖，不引入网络字体，不生成/下载图片（favicon 用内联 SVG data URI）。
- `html` 常驻 `class="dark"`，不做明暗切换；删除 `index.css` 的 `.dark` 块，深色值写进 `:root`。
- 光效预算：每页最多 1 个 glow 元素（首页=Hero CTA，Focus=里程碑后的结束按钮）。
- 所有动效必须带 `motion-reduce` 降级；`prefers-reduced-motion` 下 MeteorField 整层隐藏、不挂载 Lightfall。
- `StarWall` 契约（`StarWallRendererProps`/`WallDay`/`state`/`level`）与 `StepProps` 签名不变。
- 前端验证：每个批次结束时 `cd frontend; npm run lint`（0 error，允许既有 button.tsx fast-refresh warning）+ `npm run build` 通过；批 2 另跑 `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py`。
- 后端零改动；token 映射修正导致全站（含未重排的结算/信箱）一次性变深色是预期效果，不得回退。

## Review Focus

Spec 未覆盖、最容易咬人的五类失败模式（每条的验证步骤已挂到对应任务）：

1. **token 修复后旧页面浅色文字落在浅底**：批 1 完成后结算/信箱虽变深色，但个别写死亮色 className 的组件可能不可读 → Task 3 增加人工核对步骤（DevTools 抽查 SettlePage/MailboxPage）。
2. **WebGL2 不可用或 `prefers-reduced-motion` 时 Focus 计时/结束流程中断**：Lightfall 只是背景层，不能影响轮询与 POST /end → Task 12 增加 DevTools 模拟 reduce + 禁用 WebGL 的人工核对。
3. **Modal 遮罩/Esc 关闭逻辑被样式改动波及**：`onClose` 行为是信件/记录弹窗的唯一关闭入口 → Task 5 保留 useEffect 与 onClick 逐行不动，人工核对。
4. **移动端 <640px 票据横向溢出或按钮点不到**：LetterTicket 被 4 处复用，一处坏处处坏 → Task 15 增加 375px 宽度人工核对。
5. **AccountSwitcher 改文字链接后登录/登出/切账号回归**：顶栏是全站唯一账号操作入口 → Task 6 人工走一遍三条路径。
6. **拟态描边误伤 SplitEditor 年/月/日下拉**：spec 明确要求只有目标输入区有 conic 描边 → Task 8 人工核对下拉无描边。

---

## 批 1（spec §5.5）：token 基线 + 顶栏 + 首页 + 认证 + Focus

### Task 1: index.html 文档外壳

**Files:**
- Modify: `frontend/index.html`

**Interfaces:**
- Consumes: 无
- Produces: `<html class="dark" lang="zh-CN">`（后续所有深色 token 的前提）

- [ ] **Step 1:** 按 spec §5.5-1 修改 `index.html`：`lang="zh-CN"`、`<html>` 加 `class="dark"`、`<title>NovaStart · 每天五分钟</title>`、favicon 换内联 SVG 星星 data URI（不新增文件）。
- [ ] **Step 2:** `cd frontend; npm run build` 通过（此步先不改 token，构建应无差异）。
- [ ] **Step 3:** Commit: `feat(frontend): dark html shell for visual refresh`

### Task 2: index.css token 重写 + 工具类

**Files:**
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: Task 1 的 `html.dark`
- Produces: spec §5.1 全部 token（`--surface-1/2`、`--glow`、`--glow-spread` 等）；工具类 `.space-glow`、`.focus-backdrop`、`.focus-backdrop--milestone`、`.btn-glow`、`.glass-form`、`.meteor-field` 及对应 keyframes；保留 `--star-*` token（只允许提亮，语义不动）

- [ ] **Step 1:** 按 spec §5.1 表格重写 `:root`：删除 `.dark` 重复块，写入全部 token 的精确值；`--card: var(--surface-1)`、`--popover: var(--surface-2)` 等别名照 spec §5.1 末两条。
- [ ] **Step 2:** 新增工具类：`.space-glow`（两层 radial-gradient 紫斑 + 底部 vignette）、`.focus-backdrop`（顶部紫光晕 + 底部 vignette）与 `.focus-backdrop--milestone`（提高光晕）、`.btn-glow`（移植 `docs/design/网站功能按钮排版和风格参考.md` 的三层 box-shadow + text-shadow + `::after` 反光，尺寸按 `h-10 px-8 rounded-xl` 收敛，transition 300ms）、`.glass-form`（渐变 + 1px 白色低透明边框 + 外发光 + backdrop-blur，参考 `docs/design/登录和注册页面的框.md`）、`.meteor-field` 与流星 keyframes（6 颗时长/延迟用 spec §5.3 值）。
- [ ] **Step 3:** `npm run build` 通过（映射还是旧的 `hsl(var(--x))`，产物无效但不报错——Task 3 修）。
- [ ] **Step 4:** Commit: `feat(frontend): dark-space token set and effect utilities`

### Task 3: tailwind.config.ts 映射修复

**Files:**
- Modify: `frontend/tailwind.config.ts:15-63`

**Interfaces:**
- Consumes: Task 2 的 token
- Produces: 所有颜色映射为 `var(--x)`（不再包 `hsl()`）；新增 `colors.surface`（`DEFAULT`/`1`/`2`）、`colors.glow`（`DEFAULT`/`spread`）、`colors.destructive.foreground`；`keyframes`/`animation` 新增 `spin-slow`（6s linear infinite）

- [ ] **Step 1:** 把 `colors` 下所有 `'hsl(var(--x))'` 改为 `'var(--x)'`；补 `surface`、`glow`（spec §5.1 的代码块原样采用）、`destructive: { DEFAULT, foreground }`。
- [ ] **Step 2:** `extend.keyframes` 加 `spin-slow: { to: { transform: "rotate(360deg)" } }`，`extend.animation` 加 `"spin-slow": "spin-slow 6s linear infinite"`。
- [ ] **Step 3:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 4（人工核对）:** `npm run dev` 打开首页 + `/settle` + `/mailbox`：DevTools 确认 `body` 的 `background-color`/`color` 解析为有效 oklch（非 `rgba(0,0,0,0)`）；结算/信箱未重排但应为深色底、文字可读（Review Focus #1）。
- [ ] **Step 5:** Commit: `fix(frontend): map color tokens via var() so oklch values resolve`

### Task 4: Button glow variant

**Files:**
- Modify: `frontend/src/components/ui/button.tsx:11-22`

**Interfaces:**
- Consumes: Task 2 的 `.btn-glow`
- Produces: `ButtonProps` 新增可选 `variant="glow"`（cva variants 加一行 `glow: "btn-glow ..."`），其余 variant/base/size 不变

- [ ] **Step 1:** `variants.variant` 新增 `glow`，类名以 Task 2 的 `.btn-glow` 为主、按 spec §5.3 尺寸收敛；不改 base 与其它 variant。
- [ ] **Step 2:** `npm run lint` 0 error（允许既有 fast-refresh warning）+ `npm run build` 通过。
- [ ] **Step 3:** Commit: `feat(frontend): add glow button variant`

### Task 5: Modal 深色面板

**Files:**
- Modify: `frontend/src/components/ui/modal.tsx`

**Interfaces:**
- Consumes: Task 3 的 `bg-surface-2`
- Produces: props 签名（`open`/`onClose`/`title`/`children`/`maxWidth`）不变

- [ ] **Step 1:** 按 spec §5.4 Modal：遮罩改 `bg-background/70 backdrop-blur-sm`；面板改 `rounded-2xl border border-border/70 bg-surface-2 p-6 shadow-[0_24px_80px_-24px_rgba(0,0,0,0.9)]`；标题上方加静态 eyebrow `NOVASTART`（`font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground`）；进出场沿用 tailwindcss-animate 的 `animate-in fade-in zoom-in-95 duration-200`。
- [ ] **Step 2:** **Esc 监听 useEffect 与遮罩 onClick 逐行保留**（Review Focus #3）。
- [ ] **Step 3:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 4:** Commit: `feat(frontend): restyle modal panel for dark surface`

### Task 6: App.tsx 顶栏 + AccountSwitcher

**Files:**
- Modify: `frontend/src/App.tsx:18-23`
- Modify: `frontend/src/features/AccountSwitcher.tsx:27-50`

**Interfaces:**
- Consumes: Task 4 的 Button、Task 3 的 token
- Produces: 顶栏 `sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-md`；路由表与 `ProtectedRoute` 不变

- [ ] **Step 1:** `App.tsx` 重写 `<header>`：内层 `mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6`；左侧 `Link to="/"` 的 `NovaStart` 文字 + 发光小圆点（`bg-glow shadow-[0_0_12px_var(--glow)]`）；右侧登录后「信箱/记录」文字链接（`/mailbox`、`/records`，`hidden sm:flex`，等宽小标签样式）+ `<AccountSwitcher />`；未登录只显示登录/注册文字链接。Routes 部分不动。
- [ ] **Step 2:** `AccountSwitcher.tsx` 把三个按钮改为等宽文字链接形态（`font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground hover:text-foreground`）；`handleLogout`、navigate、store 调用逐行保留。
- [ ] **Step 3:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 4（人工核对）:** 走一遍登录 → 出现信箱/记录链接 → 切换账号 → 登出，三条路径行为与改动前一致（Review Focus #5）；375px 宽度顶栏不换行溢出。
- [ ] **Step 5:** Commit: `feat(frontend): sticky glass header with text nav`

### Task 7: HomePage Hero + 进度区

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`

**Interfaces:**
- Consumes: Task 4 的 `variant="glow"`、Task 2 的 `.space-glow`
- Produces: 无新签名；`StarWall`/`StreakBadge` 调用不变（本批不换皮，仍由默认渲染器渲染）

- [ ] **Step 1:** Hero 区按 spec §5.4「首页首屏」重排：`min-h-[78vh]` 居中、背景 `.space-glow`；结构 = 等宽小标签 `DAILY PRACTICE · 5 MIN` → `clamp(2.5rem,7vw,5.5rem)` 超大标题「每天五分钟」→ 次行「主动学习一点点」（同字号阶、`text-muted-foreground`）→ 一行副文案 → `Button variant="glow" size="lg"`；**删除「图片占位」块**；CTA 的 `disabled`/`onClick`/提示文案不变。
- [ ] **Step 2:** 历史三入口由 `grid` + `Button variant="outline"` 改为居中纯文字按钮（样式见 spec §5.4），三个 `onClick`（开弹窗 + 加载数据）不变。
- [ ] **Step 3:** 进度区去掉外层 `Card`/`CardContent`，改为 `border-t border-border/60 pt-10` 分区；`StreakBadge`/`StarWall` 组件调用与 props 不变。所有数据加载 effect、`handleAnalyze`/`handleUpdate`/`handleStart`/`loadLetters`/`queryRecords`/`loadReview` 逐行保留。
- [ ] **Step 4:** 「开始学习」弹窗与其它三个弹窗内容本批不动（历史信件列表批 2 才换票据）。
- [ ] **Step 5:** `npm run lint` + `npm run build` 通过；人工核对 spec 批 1 验收 #3（无图片占位、唯一 glow、三个文字入口）。
- [ ] **Step 6:** Commit: `feat(frontend): rebuild home hero with space glow and glow CTA`

### Task 8: TaskComposer 拟态输入框

**Files:**
- Modify: `frontend/src/features/task/TaskComposer.tsx:46-70`

**Interfaces:**
- Consumes: Task 3 的 `animate-spin-slow`、`bg-surface*`
- Produces: `TaskComposerProps` 签名不变

- [ ] **Step 1:** 只给目标输入区（label + input + 计数组）套拟态框，按 spec §5.4「拟态目标输入框」三层结构：外层 `relative overflow-hidden rounded-3xl bg-surface p-1.5 shadow-[...]`、描边层 `pointer-events-none absolute -inset-12 bg-[conic-gradient(...)] animate-spin-slow motion-reduce:animate-none`、内层 `relative rounded-[1.25rem] bg-surface-2 p-3`；label 改等宽小标签，input 去外边框、focus 只加 `ring-1 ring-ring`；**`maxLength`、计数、`disabled` 逻辑不变**。
- [ ] **Step 2:** 示例 chips 改胶囊描边样式；「分析」按钮保持 `default`（不用 glow）；carryOver 区块仅适配深色、逻辑不动。
- [ ] **Step 3:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 4（人工核对）:** 打开首页「开始学习」弹窗：输入框有旋转描边；同弹窗的 `SplitEditor` 与历史记录弹窗的年/月/日 `<select>` 无描边（Review Focus #6）。
- [ ] **Step 5:** Commit: `feat(frontend): mimic input shell with conic border for task composer`

### Task 9: MeteorField + 登录/注册页

**Files:**
- Create: `frontend/src/components/ui/meteor-field.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/pages/RegisterPage.tsx`

**Interfaces:**
- Consumes: Task 2 的 `.glass-form`、`.meteor-field` keyframes
- Produces: `export default function MeteorField(): JSX.Element` — 纯装饰层，6 颗 `<span className="star">`，`aria-hidden`，`pointer-events-none fixed inset-0 overflow-hidden`；`prefers-reduced-motion` 下整层 `display:none`（CSS 媒体查询实现）

- [ ] **Step 1:** 新建 `meteor-field.tsx`：按 spec §5.3 的 6 颗时长/延迟（1s/3s/2.75s/1.6s/2.2s/3.2s）渲染 span，样式类来自 Task 2 的 `.meteor-field`。
- [ ] **Step 2:** `LoginPage.tsx`/`RegisterPage.tsx`：页面容器改深色底 + `<MeteorField />` 装饰层；表单 Card 外壳换 `.glass-form`（`max-w-sm rounded-2xl p-8`）；标题两级 = 等宽 eyebrow（`SIGN IN`/`SIGN UP`）+ `-webkit-text-stroke` 拉丁主标题 `NOVASTART` + 一行中文说明；输入框深色内嵌 focus 变亮；提交按钮改紫→青渐变 + hover 扫光（本任务在 `index.css` 补 `.glass-submit` 工具类，纯 CSS 实现，`motion-reduce` 关扫光）。
- [ ] **Step 3:** **校验、`login`/`register` 请求、错误文案、navigate 跳转逐行保留。**
- [ ] **Step 4:** `npm run lint` + `npm run build` 通过；人工核对：登录成功/失败两条路径行为不变（Review Focus 关联 #3/#5 的表单回归）。
- [ ] **Step 5:** Commit: `feat(frontend): glass auth forms with meteor background`

### Task 10: Lightfall WebGL2 背景组件

**Files:**
- Create: `frontend/src/features/focus/Lightfall.tsx`（移植 `docs/design/流动背景参考代码.md` 完整实现）

**Interfaces:**
- Consumes: 无（自包含 WebGL2）
- Produces: `export interface LightfallProps`（colors/backgroundColor/speed/streakCount/streakWidth/glow/density/twinkle/zoom/bloom/intro/mouseInteraction/dpr 等，与参考源码一致）+ `export default function Lightfall(props: LightfallProps)`；WebGL2 不可用时返回 null 不渲染 canvas；卸载时 `cancelAnimationFrame`/`removeEventListener`/`deleteTexture`/`deleteProgram`

- [ ] **Step 1:** 移植参考源码全文：去掉 `'use client'` 指令；保留全部 props、着色器、resize/mouse 处理与清理逻辑（spec §5.4 Focus 页「清理」条款是硬性要求）。
- [ ] **Step 2:** `npm run lint` + `npm run build` 通过（TS 严格模式下参考代码若有 any/未用变量，最小改动修到 lint 通过，不改算法）。
- [ ] **Step 3:** Commit: `feat(frontend): port Lightfall WebGL2 background component`

### Task 11: FocusPage 背景 + 排版 + 里程碑

**Files:**
- Modify: `frontend/src/pages/FocusPage.tsx:254-298`
- Modify: `frontend/src/features/focus/FocusTimer.tsx`

**Interfaces:**
- Consumes: Task 2 的 `.focus-backdrop(--milestone)`、Task 4 的 `variant="glow"`、Task 10 的 `Lightfall`
- Produces: `Lightfall` 挂载参数照 spec §5.4「Focus 页」Lightfall 参数清单原样使用；`FocusTimer` props（`elapsedSec: number`）不变

- [ ] **Step 1:** `FocusPage` 容器改 `relative isolate min-h-screen overflow-hidden`；静态层 `.focus-backdrop`（里程碑时加 `--milestone` 修饰类）常驻；`<Lightfall ... />` 绝对定位 `inset-0 -z-10`；`prefers-reduced-motion: reduce` 时不挂载 Lightfall（用 `matchMedia` 在 effect 中判定，状态只控制是否渲染背景，不接触计时逻辑）。
- [ ] **Step 2:** 排版：等宽小标签「本次专注」+ 任务首步；`FocusTimer` 内部数字字号改 `clamp(3.5rem,12vw,5rem) font-mono tabular-nums`（格式化逻辑不动）；「结束」按钮 `variant={milestone ? "glow" : "outline"}`（5 分钟前 outline）；**所有轮询/封顶/结束/导航代码逐行保留**。
- [ ] **Step 3:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 4:** Commit: `feat(frontend): focus page Lightfall backdrop and milestone glow`

### Task 12: 批 1 验证门

**Files:** 无改动

- [ ] **Step 1:** `cd frontend; npm run lint` 0 error、`npm run build` 通过。
- [ ] **Step 2:** `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py` 通过（确认未触碰后端）。
- [ ] **Step 3（人工核对，对照 spec §3 批 1 全部 8 条）:** 重点含：DevTools 模拟 `prefers-reduced-motion: reduce` 后 Focus 页为静态渐变且计时/结束正常；禁用 WebGL（DevTools → Rendering 或 chrome://flags）后同样正常（Review Focus #2）；移动端顶栏不溢出。
- [ ] **Step 4:** 核对通过后在 spec §8 回填批 1 执行结果；有未验证项如实标注。

---

## 批 2（spec §5.6）：票据 + 结算换皮 + 星星墙/记录占位

### Task 13: card.tsx 深色面板基础样式

**Files:**
- Modify: `frontend/src/components/ui/card.tsx:11`

**Interfaces:**
- Produces: Card 圆角/边框/内高光统一（`rounded-2xl border border-border/70 bg-card shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]` 级别）；API 不变

- [ ] **Step 1:** 只改 Card 根元素的 className 常量，子组件不动。
- [ ] **Step 2:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 3:** Commit: `feat(frontend): unify card base style for dark panels`

### Task 14: LetterTicket 票据组件

**Files:**
- Create: `frontend/src/components/ui/letter-ticket.tsx`

**Interfaces:**
- Consumes: Task 3 的 `bg-surface-2`
- Produces:

```ts
export interface LetterTicketProps {
  id: number
  dateISO: string
  content: string
  counterpart: string | null
  direction: "in" | "out"
  status?: string
  actions?: ReactNode
}
export default function LetterTicket(props: LetterTicketProps): JSX.Element
```

- [ ] **Step 1:** 按 spec §5.4「票据」实现：主票（等宽标签 `FROM`/`TO` + `counterpart ?? "同学"` + 日期 + 正文 + 底部 `actions`）+ 存根（`NO. {String(id).padStart(4,"0")}` + 日期）；分隔 `border-dashed` + 两侧圆形凹口（填 `var(--background)`）；`max-w-sm bg-surface-2 rounded-2xl` 细边框；桌面 `sm:flex-row`（存根 `sm:w-32`）、移动端纵向堆叠；**不做座位号/条形码**；`status` 显示在存根或主票右上角。
- [ ] **Step 2:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 3:** Commit: `feat(frontend): add reusable letter ticket component`

### Task 15: 信箱三列表 + MailboxPage 分区

**Files:**
- Modify: `frontend/src/features/mailbox/InboxList.tsx`
- Modify: `frontend/src/features/mailbox/HistoryList.tsx`
- Modify: `frontend/src/features/mailbox/OutboxList.tsx`
- Modify: `frontend/src/pages/MailboxPage.tsx:94-137`

**Interfaces:**
- Consumes: Task 14 的 `LetterTicket`
- Produces: `InboxListProps`/`HistoryListProps`/`OutboxListProps` 签名不变

- [ ] **Step 1:** 三个列表把 `<li>` 内容换成 `LetterTicket`：Inbox/History 用 `direction="in"`（counterpart=`sender_name`，status=`focused_delivery ? "专注时投递" : undefined`），Outbox 用 `direction="out"`（counterpart=`recipient_name`，status=`已投递/未送达`）；操作按钮（收藏/放弃/删除，`busyId` 禁用逻辑不变）放进 `actions`。
- [ ] **Step 2:** `MailboxPage` 三个 Card 外壳改为等宽小标签分区（eyebrow + 标题），`refresh`/`runLetterAction`/409 文案逐行保留。
- [ ] **Step 3:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 4（人工核对）:** 375px 宽度票据纵向堆叠、无横向滚动、按钮可点；收藏一封 → 触发 409 场景时文案与刷新行为不变（Review Focus #4）。
- [ ] **Step 5:** Commit: `feat(frontend): mailbox sections render letter tickets`

### Task 16: 首页历史信件弹窗换票据

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx:326-343`

**Interfaces:**
- Consumes: Task 14 的 `LetterTicket`
- Produces: 无新签名

- [ ] **Step 1:** 「历史收藏信件」弹窗的 `<li>` 换成 `LetterTicket direction="in"`（`loadLetters` 与空态/加载态文案不变）。
- [ ] **Step 2:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 3:** Commit: `feat(frontend): reuse letter ticket in home letters modal`

### Task 17: StreakBadge + 星星墙默认渲染器换皮

**Files:**
- Modify: `frontend/src/features/progress/StreakBadge.tsx`
- Modify: `frontend/src/features/progress/StarWall.tsx:77-96`

**Interfaces:**
- Produces: `StreakBadge` props（`current`/`longest`）、`StarWallRendererProps`、`DefaultStarWallRenderer` 导出不变

- [ ] **Step 1:** `StreakBadge`：等宽标签 `CURRENT STREAK` + `text-5xl font-semibold tabular-nums` 数字 + 右侧「天连续 · 最长 X 天」。
- [ ] **Step 2:** `DefaultStarWallRenderer`：`gap` 改 `gap-2.5`，星星 `h-5 w-5 sm:h-6 sm:w-6`；点亮项（`state==="lit"`）加 `drop-shadow` 光晕（复用 `StarIcon` 的 `glow` prop）；`empty` 占位 span 尺寸同步放大、仍不绘制；`title` 文案不变。容器 `StarWall` 与契约类型一行不动。
- [ ] **Step 3:** `npm run lint` + `npm run build` 通过；人工核对星星墙三态（lit 有光晕 / dim / broken）与 empty 占位。
- [ ] **Step 4:** Commit: `feat(frontend): reskin streak badge and star wall renderer`

### Task 18: 结算流统一深色面板

**Files:**
- Modify: `frontend/src/features/focus/MilestoneBanner.tsx`
- Modify: `frontend/src/features/settle/SettleSummary.tsx`
- Modify: `frontend/src/features/settle/StepReflection.tsx`
- Modify: `frontend/src/features/settle/StepDeliver.tsx`
- Modify: `frontend/src/features/settle/StepMailbox.tsx`
- Modify: `frontend/src/features/settle/StepReview.tsx`
- Modify: `frontend/src/features/settle/CosmicWhisper.tsx`

**Interfaces:**
- Produces: 各组件 props（`StepProps` = `sessionId` + `onDone` 等）全部不变；`SettleSummary` 保留现有 framer-motion 星星缩放动画（不新增）

- [ ] **Step 1:** 各组件统一深色面板 + 等宽小标签排版（面板样式对齐 Task 13 的 Card）；文案、按钮顺序、阶段推进（`onDone` 调用时机）、请求逻辑逐行保留。
- [ ] **Step 2:** `npm run lint` + `npm run build` 通过；人工核对结算四步与末态的文案/顺序与改动前一致。
- [ ] **Step 3:** Commit: `feat(frontend): unify settle flow panels on dark surface`

### Task 19: RecordsPage 占位换皮

**Files:**
- Modify: `frontend/src/pages/RecordsPage.tsx`

**Interfaces:**
- Produces: 无

- [ ] **Step 1:** 浅色居中标题改为等宽 eyebrow `RECORDS` + 标题 + 「记录页建设中」；不实现任何查询功能。
- [ ] **Step 2:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 3:** Commit: `feat(frontend): reskin records placeholder page`

### Task 20: 批 2 验证门

**Files:**
- Modify: `docs/specs/011-visual-refresh.md`（仅 §8 回填）

- [ ] **Step 1:** `cd frontend; npm run lint` 0 error、`npm run build` 通过。
- [ ] **Step 2:** `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py` 通过。
- [ ] **Step 3（人工核对，对照 spec §3 批 2 全部 6 条）:** 信箱三类票据、移动端堆叠、409 文案、首页收藏信件票据、星星墙三态、结算四步顺序。
- [ ] **Step 4:** spec §8 回填批 2 执行结果与未验证项，区分「已运行通过」与「仅人工核对」。
- [ ] **Step 5:** Commit: `docs(spec): backfill 011 visual refresh execution results`
