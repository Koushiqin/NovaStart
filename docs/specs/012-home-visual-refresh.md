# 012 首页编辑式重构 + 三项背景/入场效果

## 1. 背景与目标

011 已把全站统一为「深空紫黑 + 霓虹紫光」。本次按用户确认的参考图与三份效果说明，把**首页**从居中式 Hero 改为左对齐编辑式（Ricardo Chance / deep-space atelier）布局，并整合三项效果：

- 首页标题逐字入场：`docs/design/首页标题加载出现动画.md`（motion-primitives `TextEffect per='char' preset='fade'`）。
- 首页背景交互：`docs/design/首页的背景效果.md`（React Bits `Galaxy`：星场漂移 + 鼠标斥力 + 点击 warp）。
- 专注页背景：`docs/design/focus的背景效果.md`（React Bits `Particles`：白色粒子 + 呼吸闪烁 + 悬停视差）。

三份 md 只有用法片段，仓库内无对应实现，且项目**不得新增依赖**（无 ogl/three）。因此按 011 的既有做法自研：`Galaxy` / `Particles` 用 Canvas2D + 离屏光晕精灵实现，`TextEffect` 用已装的 framer-motion 实现。

视觉唯一权威为 `docs/design/风格提示词.md`；需求来源仍为 `brainstorming.md`，本次不改变任何功能语义。

### 已确认决策（用户已同意 Q1–Q5）

1. 字体**自托管** woff2（`frontend/public/fonts`），不引 Google CDN，Docker 离线可用。
2. 右侧星形视觉用**纯 SVG 点云**（复用星星墙数据与 `StarIcon`），不引 Three.js。
3. 首页左上放大写 wordmark，顶栏在首页降为**仅右侧账号控件**；其他页面保留原顶栏。
4. 首页只做**一个**圆形主 CTA（Start learning），不做次按钮。
5. 三个历史入口**保留弹窗**，只换外壳，不动信息架构。

## 2. 范围与非目标

**范围**

- `frontend/index.html`：`lang="en"`、英文标题、字体 preload。
- `frontend/public/fonts/`：新增 3 个 woff2（Instrument Serif 400 / italic、Red Hat Display 400–900 变量）。
- `frontend/tailwind.config.ts`：新增 `fontFamily.display` / `fontFamily.sans`。
- `frontend/src/index.css`：`@font-face`、深空背景 token、`.cosmos-sky`、星星三档改单色相（白/淡紫）。
- 新增 `frontend/src/components/core/text-effect.tsx`（逐字入场）。
- 新增 `frontend/src/components/ui/galaxy.tsx`（首页背景）。
- 新增 `frontend/src/components/ui/particles.tsx`（专注页背景）。
- `frontend/src/pages/HomePage.tsx`：首屏与进度区重排为四象限，数据逻辑逐行保留。
- `frontend/src/pages/FocusPage.tsx`：背景层由 Lightfall 换为 Particles；计时/轮询/结束逻辑不动。
- `frontend/src/App.tsx`：顶栏按路由形态切换（首页仅右侧控件）。
- `frontend/src/features/progress/StreakBadge.tsx`、`StarWall.tsx`：首页用单行连续天数 + 新增紧凑渲染器。
- `frontend/src/components/ui/modal.tsx`、`button.tsx`：直角玻璃面板、新增 `frost` 圆形按钮 variant。

**非目标**

- 不改后端、数据库、Alembic、API 请求/响应契约。
- 不改 `StarWallRendererProps` / `WallDay` / `state`·`level` 语义（只新增一个渲染器）。
- 不改 `streak`、`progress`、`session` 的任何计算：连续天数、亮度分级仍只由服务端给出。
- 不动登录/注册、结算、信箱、记录页的现有视觉与逻辑。
- 不新增任何 npm 依赖、不生成图片资源、不引网络字体。
- 不做明暗主题切换。
- 不做滚动驱动的一页式长首页：本次只重排首屏与进度区，历史入口仍是弹窗。

## 3. 可测试的验收条件

1. 首页 `<html lang>` 为 `en`；首屏文案全英文（eyebrow / 标题两行 / 简介 / CTA / 三个链接 / 星星区标签），不再出现中文 Hero 文案。
2. 首页标题使用 Instrument Serif 400 斜体，第二行透明度约为第一行的 60%；标题以逐字 fade 入场，字符依次出现。
3. 首页存在全屏背景：`linear-gradient(180deg,#050505 40%,#0d0718 100%)` + 两层紫色 radial + 星点；其上叠加 Galaxy Canvas 星场，鼠标移入可见星点被推开，点击可见短暂 warp（旋转加速）。
4. `prefers-reduced-motion: reduce` 时标题直接显示完整文本、Galaxy/Particles 不持续动画（只渲染静态帧或整层不挂载），页面内容完整可读。
5. 首页顶栏只剩右侧账号控件（无品牌文字、无「信箱/记录」导航）；其余路由顶栏与改动前一致。
6. 首页首屏只有一个圆形 `Start learning` 主 CTA（毛玻璃、无 box-shadow），左下为三个衬线体下划线文字链接，点击分别打开原有三个弹窗且内容/请求不变。
7. 右下角显示连续天数单行文本（`N-day streak · longest M`）与 30 天紧凑星星墙；数值来自 `GET /api/progress/summary`，未登录时显示引导文案而非伪造数据。
8. Focus 页挂载 Particles 白色粒子背景（悬停视差、闪烁），`.focus-backdrop` 静态层保留兜底；计时、15s 轮询、结束/无效差额流程与改动前完全一致。
9. `cd frontend; npm run lint` 0 error（允许既有 `button.tsx` fast-refresh warning）；`npm run build` 通过。
10. `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py` 仍通过（前端改动不触碰后端棘轮）。

## 4. 现有 owner 和受影响模块

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `frontend/src/index.css` | 颜色/字体/背景唯一来源 | 新增 `@font-face`、`.cosmos-sky`；背景与星星 token 调向参考配色 |
| `frontend/tailwind.config.ts` | token → Tailwind 映射 | 仅新增 `fontFamily` |
| `frontend/index.html` | 文档外壳 | `lang="en"`、英文标题、字体 preload |
| `frontend/public/fonts/*.woff2` | 自托管字体 | 新增 3 个文件 |
| `frontend/src/components/core/text-effect.tsx` | 新增逐字动画原语 | 新增文件（被首页标题复用） |
| `frontend/src/components/ui/galaxy.tsx` | 新增首页背景 | 新增文件，纯展示、无状态 |
| `frontend/src/components/ui/particles.tsx` | 新增专注页背景 | 新增文件，纯展示、无状态 |
| `frontend/src/pages/HomePage.tsx` | 首页 | 只重排 JSX 与样式；取数、弹窗、分析/开始逻辑逐行保留 |
| `frontend/src/pages/FocusPage.tsx` | 专注页 | 替换背景挂载；计时/轮询/结束代码不动 |
| `frontend/src/App.tsx` | 路由外壳 + 顶栏 | 顶栏按 `pathname` 切换形态，路由表不变 |
| `frontend/src/features/progress/StreakBadge.tsx` | 连续天数展示 | 改单行排版，props 不变 |
| `frontend/src/features/progress/StarWall.tsx` | 星星墙 | 新增 `CompactStarWallRenderer`，默认渲染器与契约不变 |
| `frontend/src/components/ui/modal.tsx` | 弹窗面板 | 直角玻璃 + hairline，去掉大阴影；Esc/关闭逻辑不变 |
| `frontend/src/components/ui/button.tsx` | 按钮 API | 新增 `frost` variant，其它 variant 不变 |
| `frontend/src/features/focus/Lightfall.tsx` | 原专注页背景 | 保留文件但不再挂载（Spec 第 8 节记录） |
| `backend/**` | 不动 | 无 |

关键事实 owner 不变：时间仍走后端 `Clock` + `useServerClock`；连续天数与星星亮度仍只由 `GET /api/progress/summary` 给出；session/结算/信箱状态仍以 PostgreSQL 与现有 API 为唯一真相源。

## 5. 实现步骤

1. **字体**：`index.html` 加 preload；`index.css` 加 3 条 `@font-face`（`font-display: swap`）；`tailwind.config.ts` 加 `fontFamily.display`（Instrument Serif + 衬线兜底）与 `fontFamily.sans`（Red Hat Display + 系统中文字体兜底）；`body` 使用 `font-sans`。
2. **背景 token**：`--star-level-1/2/3` 改为同色相白/淡紫三档；新增 `.cosmos-sky`（三层渐变 + 低透明度星点）供首页使用；`.focus-backdrop` 保留。
3. **TextEffect**（`components/core/text-effect.tsx`）：按词分组、词内逐字 `motion.span`，`staggerChildren` 驱动；`preset: 'fade' | 'blur' | 'slide'`；容器加 `sr-only` 完整文本保证可读；`useReducedMotion()` 为真时直接渲染纯文本。
4. **Galaxy**（`components/ui/galaxy.tsx`）：Canvas2D + 离屏径向光晕精灵；螺旋臂分布星点、缓慢自转；`mouseRepulsion` 在半径内推开星点并带回落；`clickWarp` 在点击后短时提高角速度并做径向脉冲；`dpr` 上限 1.5；`ResizeObserver` 重排；卸载时取消 rAF、移除监听、断连观察器；reduce 时只画一帧。
5. **Particles**（`components/ui/particles.tsx`）：Canvas2D 白色粒子；`twinkle` 控制透明度呼吸、`glow` 控制光晕精灵、`hoverEffect="parallax"` 按深度位移；reduce 时只画一帧；同样做清理。
6. **首页布局**（`HomePage.tsx`）：
   - 首屏 `min-h-screen` + `.cosmos-sky` + `<Galaxy />` 绝对底层；
   - 左上 wordmark `NOVASTART`（Red Hat Display 600 大写、宽字距）+ 发光小点；
   - 左中 eyebrow `DAILY PRACTICE · FIVE MINUTES` → 衬线斜体两行标题（第二行 60%）→ 英文简介 → 圆形 `Start learning`；
   - 左下三个衬线体下划线链接（Saved letters / Learning log / Random reflection），点击行为复用 `loadLetters` / `queryRecords` / `loadReview`；
   - 右下 `YOUR SKY` + 单行连续天数 + 紧凑星星墙；未登录显示引导文案；
   - 保存弹窗与全部数据逻辑不变。
7. **专注页**：`FocusPage.tsx` 用 `<Particles ... />` 替换 `<Lightfall />` 挂载参数；`focus-backdrop` 保留为静态兜底；其余代码不动。
8. **外壳**：`App.tsx` 用 `useLocation`，首页只渲染右侧 `AccountSwitcher`；其余路由保留原顶栏；`Modal` 改直角玻璃；`Button` 加 `frost`；`StreakBadge` 改单行；`StarWall` 加 `CompactStarWallRenderer` 并在首页注入。
9. 跑 `npm run lint`、`npm run build`、后端棘轮，回填第 8 节。

## 6. 接口、数据及兼容性变化

- 后端 API / 数据库 / Alembic：**无**。
- `StarWallRendererProps`、`WallDay`、`state`/`level` 语义不变；只新增 `CompactStarWallRenderer` 导出，默认渲染器保持。
- `StreakBadge` props `{ current, longest }` 不变（仅排版改英文单行）。
- `Button` 新增可选 `variant="frost"`，向后兼容；`Modal` props 不变。
- 新增 3 个前端组件文件 + 3 个字体文件，均属新增而非改既有契约；理由：TextEffect 与两套背景各自独立、仅各自页面使用。
- `Lightfall.tsx` 保留但不再挂载，属可回退项，不删除。

---

> 结构性变更五问：
> 1. **修改哪一层？** 仅前端展示层（`index.css` / tailwind / `pages` / `features` / `components/ui`）与字体静态资源；后端零改动。
> 2. **当前 owner 在哪里？** 颜色/字体/背景 = `index.css` + `tailwind.config.ts`；星星亮度 = `--star-*`；连续天数与墙数据 = `GET /api/progress/summary`；时间 = 后端 `Clock` + `useServerClock`。
> 3. **是否引入重复状态或平行写入？** 否。Galaxy / Particles / TextEffect 均为无状态纯展示组件，不读写 store、不发请求。
> 4. **是否影响接口和其他模块？** 否。API 契约不变；`StarWall` 与结算组件签名不变；`Button`/`Modal` 变更向后兼容。
> 5. **哪些现有检查需要继续通过？** `backend/tests/test_architecture.py`（棘轮）、`npm run lint`、`npm run build`；不新增测试依赖、不放宽任何检查。

## 7. 测试场景与验证命令

```powershell
cd frontend; npm run lint; npm run build
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py
```

人工核对（`npm run dev`）：

- 首页：英文文案齐全、标题逐字入场、第二行 60% 透明度、单一圆形 CTA、三个链接可打开原弹窗、右下连续天数与星星墙。
- 背景：星场可见缓慢自转；鼠标移入星点被推开；点击出现短暂加速/脉冲。
- 降级：系统开启「减少动态效果」后刷新，标题一次显示完整、背景不再持续动画、页面内容不缺失。
- 顶栏：`/` 只剩右侧账号控件；`/records`、`/mailbox`、`/focus` 顶栏与改动前一致。
- 专注页：白色粒子可见、悬停有视差、5 分钟前后按钮与结束流程不变。
- 字体：DevTools `Computed → font-family` 为 `"Instrument Serif"` / `"Red Hat Display"`，Network 中 woff2 由本地 `/fonts/` 加载（无 fonts.gstatic.com 请求）。

## 8. 执行结果、未验证项和遗留问题

（回填于 2026-11-08）

### 已运行通过（有命令输出）

| 检查 | 命令 / 方式 | 结果 |
|---|---|---|
| 前端 lint | `cd frontend; npm run lint` | 0 error，仅既有 `button.tsx` fast-refresh warning |
| 前端 build | `cd frontend; npm run build` | 通过，2546 modules，4.09s |
| 后端棘轮 | `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py` | 77 passed |
| 字体产物 | `Get-ChildItem frontend\dist\fonts` | 3 个 woff2 已随构建复制（22.1KB / 21.0KB / 30.7KB） |
| CSS 静态核验 | 构建产物正则计数 | `@font-face` ×3、`cosmos-sky` ×1、`star-level-3` ×3，字体与背景类均已生成 |
| 浏览器核对（首页） | `npm run dev -- --port 5191`，浏览器打开 `http://localhost:5191/` | PASS：两行标题均为 `Instrument Serif` 且 `font-style: italic`；圆形 `Start learning` 按钮（128×128，`border-radius: 9999px`）；三条下划线链接齐全；深紫黑星空背景（canvas 存在）；控制台无 error |

### 验收条件逐条状态

1. `lang="en"` + 英文首屏文案 — **已运行验证** PASS。
2. 衬线斜体标题 + 第二行 60% + 逐字入场 — 字体与斜体、透明度 **已运行验证**；逐字动画为代码级确认（framer-motion `staggerChildren`），运行时段落级核对未做。
3. 三层渐变 + 星点 + Galaxy 星场 — 背景与 canvas **已运行验证**；鼠标斥力 / 点击 warp 为代码级确认，**未做交互核对**。
4. `prefers-reduced-motion` 降级 — 代码级：`useReducedMotion()` 直出纯文本；Galaxy/Particles 命中 reduce 时只画一帧不启动 rAF。**未运行时核对**。
5. 首页顶栏仅右侧控件 — 代码级 `AppHeader` 按 `pathname === "/"` 分支；**未运行时核对**（未登录态右侧控件已随页面渲染，但未逐项截图比对其他路由）。
6. 单一圆形 CTA + 三个链接 — **已运行验证** PASS；三个弹窗内容复用原逻辑，**弹窗内数据请求未运行时核对**（需登录态）。
7. 右下连续天数 + 紧凑星星墙 — 代码级：`CompactStarWallRenderer` 接入，数据仍取 `GET /api/progress/summary`；未登录显示引导文案。**登录态未运行时核对**。
8. Focus 页 Particles — 代码级替换挂载且保留 `.focus-backdrop` 兜底；计时/轮询/结束代码未改动。**未运行时核对**（需登录 + 活动会话）。
9. lint / build — **已运行验证** PASS。
10. 后端棘轮 — **已运行验证** PASS。

### 遗留问题

- `frontend/src/features/focus/Lightfall.tsx` 保留但不再被任何页面挂载，作为专注页背景的可回退方案；如需彻底移除，另起一次清理改动。
- 登录态相关的三处核对（首页星星区、三个历史弹窗、Focus 粒子背景）需人工在浏览器补做。
- 移动端（<1024px）两列堆叠后的阅读顺序为「标题 → CTA → 链接 → 天空」，未逐断点核对。
- 本 Spec 未新增任何 npm 依赖；字体为自托管 woff2，`dist` 中已随构建产出，Docker 离线可用。
