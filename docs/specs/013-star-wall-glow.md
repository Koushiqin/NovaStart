# 013 首页星星墙放大 + 发光闪烁

## 1. 背景与目标

012 首页视觉改版后，右下角紧凑星星墙的星星为 14px（`h-3.5 w-3.5`），在当前深空背景上偏小、偏静。本次只调整首页星星墙的**视觉呈现**：

- 放大星星图像，让 30 天点云更易辨认。
- 已点亮星星增加发光 + 呼吸闪烁效果，强化「点亮」的成就感。

需求不涉及任何数据、接口或状态语义变化。

## 2. 范围与非目标

- 范围：`frontend/src/features/progress/StarWall.tsx` 的 `CompactStarWallRenderer`；`frontend/src/index.css` 新增光晕 token、闪烁动画与 reduced-motion 降级。
- 非目标：不改 `StarWall` 容器契约、`WallDay`/`state`·`level` 语义、`StarIcon` 对外 API；不改 `DefaultStarWallRenderer`（结算/记录页外观不受影响）；不改后端、API、数据库；不新增依赖、不生成图片资源；不做明暗主题。

## 3. 可测试的验收条件

1. 首页右下角星星墙每颗星星渲染尺寸为 `h-6 w-6`（24px），空白天占位同步为 `h-6 w-6`，10 列网格在 375px 宽度下不横向溢出。
2. `state === "lit"` 的星星带 `star-twinkle` 类，动画周期约 3.6s，透明度 / 缩放 / 外发光在 0% 与 50% 之间循环。
3. 每颗点亮星星的 `animation-delay` 由序号推导、彼此不同，整墙不同步呼吸。
4. `dim` / `broken` 星星尺寸放大但**不**发光闪烁，三态语义仍可从外观区分。
5. `prefers-reduced-motion: reduce` 下 `.star-twinkle` 不播放动画，仅保留静态外发光。
6. `cd frontend; npm run lint` 0 error；`npm run build` 通过。
7. `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py` 仍通过。

## 4. 现有 owner 和受影响模块

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `frontend/src/index.css` | 颜色/动画唯一来源 | 新增 `--star-glow` token、`.star-twinkle` 工具类、`@keyframes star-twinkle`、reduced-motion 降级 |
| `frontend/src/features/progress/StarWall.tsx` | 星星墙渲染器 | 仅改 `CompactStarWallRenderer` 尺寸、间距、闪烁类与延迟；数据与契约不动 |
| `frontend/src/pages/HomePage.tsx` | 调用方 | 不改 |
| `frontend/src/features/focus/MilestoneBanner.tsx`、`features/settle/SettleSummary.tsx` | 复用 `StarIcon` | 不改 |

关键事实 owner 不变：星星状态与亮度仍只由 `GET /api/progress/summary` 的 `state`/`level` 决定；前端只做展示。

## 5. 实现步骤

1. `index.css`：在 `--star-*` token 组新增 `--star-glow`（与星空同一紫白色相）；新增 `.star-twinkle`（`animation: star-twinkle 3.6s ease-in-out infinite`）；新增 `@keyframes star-twinkle`（透明度 + 缩放 + 双层 `drop-shadow`）；在 `prefers-reduced-motion` 块中关闭动画、保留静态光晕。
2. `StarWall.tsx` 的 `CompactStarWallRenderer`：容器与占位由 `h-3.5 w-3.5` 放大为 `h-6 w-6`，间距调整为 `gap-x-2 gap-y-2`；点亮星星加 `star-twinkle` 类并按序号写入 `animationDelay`；`dim`/`broken` 不参与闪烁。
3. 跑 lint / build / 后端棘轮，回填第 8 节。

## 6. 接口、数据及兼容性变化

- 无 API、数据库、Alembic 变化。
- 无组件 props / 类型签名变化；`CompactStarWallRenderer` 输出视觉变化，`DefaultStarWallRenderer` 与 `StarIcon` 保持原样。
- 新增一个 CSS 变量与一个工具类，均为前端内部样式。

## 7. 测试场景与验证命令

```powershell
cd frontend; npm run lint; npm run build
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py
```

人工核对（登录态首页）：

- 右下班星星墙星星明显变大，3 行 10 列不溢出容器。
- 已点亮星星有柔和外发光并错峰呼吸；暗星与断签空心星不闪烁。
- 系统开启「减少动态效果」后刷新，星星不再闪动、仍有静态光晕。

## 8. 执行结果、未验证项和遗留问题

（回填于 2026-11-08）

### 已运行通过（有命令输出）

| 检查 | 命令 / 方式 | 结果 |
|---|---|---|
| 前端 lint | `cd frontend; npm run lint` | 0 error，仅既有 `button.tsx` fast-refresh warning |
| 前端 build | `cd frontend; npm run build` | 通过，2546 modules，2.32s |
| 后端棘轮 | `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py -q` | 77 passed |
| 构建产物核验 | 对 `frontend/dist/assets/*.css` 正则计数 | `star-twinkle` 出现 4 次、`star-glow` 出现 5 次，动画与变量已进入产物 |

### 验收条件逐条状态

1. 星星与空白天占位统一 `h-6 w-6`（24px）、10 列 `gap-x-2` — **代码级 + 构建验证**；375px 实际渲染未截图核对。
2. 点亮星星带 `star-twinkle`，3.6s 循环透明度/缩放/双层外发光 — **代码级 + 产物验证**。
3. 延迟按序号 `(index * 0.31) % 3.6` 注入 — **代码级**。
4. `dim` / `broken` 仅放大、不闪烁 — **代码级**（仅 `lit` 加类）。
5. `prefers-reduced-motion: reduce` 关闭动画、保留静态光晕 — **代码级**。
6. lint / build — **已运行验证** PASS。
7. 后端棘轮 — **已运行验证** PASS。

### 未验证项

- 未在登录态浏览器中实际观察 30 天星星墙的放大尺寸、错峰闪烁与不同断点下不溢出的表现（需登录 + 后端 + PostgreSQL）；建议 `npm run dev` 后人工核对。

### 遗留问题

- 无新增依赖；`DefaultStarWallRenderer` 与 `StarIcon` 未改动，其他页面外观不受影响。

