# 010 星星墙预留美化接口

## 1. 背景与目标

星星墙（`frontend/src/features/progress/StarWall.tsx`）当前把「视觉布局」与「数据契约」写在同一个组件里，后续单独美化星星墙时不得不改动包含 `WallDay`/`ProgressSummaryData` 类型与状态语义的文件。

目标：把星星墙拆成「容器（数据） + 可替换渲染器（视觉）」，预留一个稳定的美化接口，让后续换皮只新增渲染器、不改数据来源与状态语义。

## 2. 范围与非目标

**范围**：
- `StarWall.tsx` 导出渲染器契约 `StarWallRendererProps` / `StarWallRenderer`。
- 抽出默认渲染器 `DefaultStarWallRenderer`（即现有布局，行为完全不变）。
- 默认导出 `StarWall` 改为容器，接受可选 `renderer` prop，缺省用默认渲染器。

**非目标**：
- 不改变视觉呈现（默认渲染器与原实现逐像素一致）。
- 不改后端接口、`WallDay` 字段或 `state/level` 语义。
- 不新增依赖、不改调用方（`HomePage` 仍只传 `wall`）。

## 3. 可测试的验收条件

1. `HomePage` 中 `<StarWall wall={progress.wall} />` 不传 renderer 时，渲染结果与改动前一致（10 列网格、empty 不绘制、三态 title）。
2. 传入自定义 `renderer` 时，容器把 `wall` 原样交给该渲染器，由渲染器决定输出。
3. `StarIcon` 的既有导出与用法（`MilestoneBanner`、`SettleSummary`）不受影响。
4. `npm run lint` 0 error、`npm run build` 通过。

## 4. 现有 owner 和受影响模块

| 模块 | 角色 | 改动 |
|---|---|---|
| `frontend/src/features/progress/StarWall.tsx` | 星星墙组件（数据契约 + 默认视觉） | 拆分容器与渲染器，新增接口类型 |
| `frontend/src/pages/HomePage.tsx` | 调用方 | 不改（仅传 `wall`） |
| `frontend/src/features/focus/MilestoneBanner.tsx` | 复用 `StarIcon` | 不改 |
| `frontend/src/features/settle/SettleSummary.tsx` | 复用 `StarIcon` | 不改 |

## 5. 实现步骤

1. 新增 `StarWallRendererProps`、`StarWallRenderer` 类型。
2. 把原渲染逻辑抽为 `DefaultStarWallRenderer`。
3. `StarWall` 默认导出改为容器，`renderer` 可选、默认 `DefaultStarWallRenderer`。
4. 跑 `npm run lint` + `npm run build`。

## 6. 接口、数据及兼容性变化

- 新增前端类型导出：`StarWallRendererProps`、`StarWallRenderer`、`DefaultStarWallRenderer`。
- `StarWall` props 从 `{ wall }` 扩展为 `{ wall, renderer? }`，向后兼容。
- 后端与数据库无变化。

## 7. 测试场景与验证命令

```powershell
cd frontend; npm run lint; npm run build
```

人工核对：首页星星墙外观与改动前一致；在 `HomePage` 临时传入自定义 renderer 可生效（验证后还原）。

## 8. 执行结果、未验证项和遗留问题

### 执行结果

- `StarWall.tsx` 已拆为容器 + `DefaultStarWallRenderer`，新增 `StarWallRendererProps` / `StarWallRenderer` 契约；`StarWall` 支持可选 `renderer`，缺省行为与原实现一致。
- `HomePage`、`MilestoneBanner`、`SettleSummary` 均未改动，`StarIcon` 导出不变。
- `npm run lint`：0 error（仅 `button.tsx` 既有 fast-refresh warning）；`npm run build`：通过。

### 未验证项
- 自定义 renderer 注入仅做类型与构建层面验证，未做浏览器实际换皮演示（当前无第二套渲染器）。

### 遗留问题
- 后续美化时，建议新增 `StarWallPro.tsx` 实现 `StarWallRenderer`，并在 `HomePage` 传入 `renderer`；数据层无需改动。
