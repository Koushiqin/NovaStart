# P5 · F7 星星与连续天数实现计划

> **For agentic workers:** 按 `.agents/skills/executing-plans` 逐任务执行。步骤用 `- [ ]` 追踪。

**Goal:** 首页星星墙（最近 30 天，亮/暗/空心三态）+「连续 X 天 · 最长 Y 天」；有效满 5 分钟点亮 Lv1，当天有效累计 15 分钟 Lv2、25 分钟 Lv3 封顶，只升不降；一天只 +1；断签次日归零并保留历史最长；结算页补上星星动画与连续天数（填 P4 槽位）。

**Architecture:** 新增 `stars`（user_id+date 唯一，minutes/level）与 `streaks`（user_id 主键）两表。单一写入路径：`progress_service.recompute_day(db, user_id, date)` 从有效会话重算当天 stars（幂等），`mark_day_completed` 维护 streak；两个调用点都在 session_service——懒标记满 5 分钟处、end 有效结束处。断签归零采用读侧懒计算（last_completed_date 与今天比较），不写后台任务。种子数据改为造完会话后跑同一 recompute 路径。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic；React 18 + framer-motion ^11（已装，仅星星点亮动画）。

**Spec:** [docs/specs/005-f7-star-streak.md](../../../docs/specs/005-f7-star-streak.md)（执行时从模板复制）。

**Depends on:** P3（有效/无效会话语义、归属日）、P4（summary 扩展点、SettleSummary 槽位）。

**Produces（后续计划依赖的接口）:**
- `GET /api/progress/summary` → `{today: {minutes, level}, streak: {current, longest, was_reset}, wall: [{date, state, level}]（最近 30 天）, server_time}`；`state ∈ "lit" | "dim" | "broken" | "empty"`（dim=今天未点亮；broken=首颗星星之后漏掉的自然日；empty=首日之前）。
- P4 summary 扩展字段生效：`star_level: int | null`、`streak: {current, longest, was_reset} | null`（字段名已在 P4 固定，此处填值）。
- 「当天是否完成」判定口径（P6 收信门槛复用）：`streak.last_completed_date == Clock.today()` 或当天 stars.level ≥ 1。

## Global Constraints

- 同 P1 全部；另：亮度只升不降；无效场次（discarded）对 stars/streak 零贡献；所有「今天」判定走 `Clock`（Asia/Shanghai）；归属日一律取 `started_at` 日期，统一表达式 `cast(func.timezone("Asia/Shanghai", Session.started_at), Date)`（禁止裸 cast）；有效场次 = `status IN ('completed','settled') AND ended_at IS NOT NULL`，discarded 与进行中场次一律排除。
- 星星/连续天数只在服务端计算，前端不做任何天数推算。

## Review Focus

1. 边界分钟：5→Lv1、14→Lv1、15→Lv2、24→Lv2、25→Lv3、40→Lv3（Task 2 钉住）。
2. 当天两场有效（如 5+12 分钟）→ minutes 累计 17 → Lv2，连续天数只 +1（Task 2 钉住）。
3. 跨零点：23:58 开始、00:03 满 5 分钟 → 星星落在 23:58 那天（Task 2 Clock 注入钉住）。
4. 断签：昨天有、前天无 → current=1 且 `was_reset=true`；longest 不回退（Task 2 钉住）。
5. discarded 场次当天无其他有效场 → 不产生星星、streak 不变（Task 2 钉住）。

---

### Task 1: 写 Spec 005

- [ ] **Step 1:** 从模板复制填写：范围=F7 全部规则 + 第 4 节 R1–R7（含 A5/A7）；非目标=信箱（P6）、记录页（P8）；验收条件含演示验收「种子连续 6 天，今天完成看到 7 天」；第 6 节写明两张新表迁移与 summary 扩展字段。
- [ ] **Step 2: Commit** `docs: spec 005 f7 star streak`

### Task 2: 后端 stars/streaks + progress 接口

**Files:**
- Create: `backend/app/models/star.py`、`streak.py`、`backend/app/services/progress_service.py`、`backend/app/routers/progress.py`、`backend/app/schemas/progress.py`、`backend/tests/test_progress.py`、迁移 `<new>_stars_streaks.py`
- Modify: `backend/app/models/__init__.py`、`backend/app/main.py`、`backend/app/services/session_service.py`（两个调用点）、`backend/app/seed.py`（种子走 recompute）、P4 的 summary service（填 star_level/streak）

**Interfaces:**
- Consumes: P3 的懒标记/end 钩子、归属日口径；P4 summary 字段位。
- Produces: `recompute_day(db, user_id, date) -> Star`、`mark_day_completed(db, user_id, date) -> Streak`；本计划头部 Produces 的 `GET /api/progress/summary`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.parametrize("minutes,level", [(5,1),(14,1),(15,2),(24,2),(25,3),(40,3)])
async def test_star_levels(db, minutes, level): ...        # 造对应时长的有效会话 → recompute 后 level 匹配
async def test_two_sessions_accumulate_one_increment(db): ...  # 5+12 → minutes=17, streak +1 只一次
async def test_cross_midnight_attributed_to_start_day(db): ...  # 23:58 开始 → star.date == 开始日
async def test_break_resets_keeps_longest(db): ...         # 造断档 → current 读侧归零, was_reset=True, longest 不变
async def test_discarded_contributes_nothing(db): ...      # 仅 discarded → 无 star, streak 不变
async def test_summary_wall_states(db): ...                # lit/dim/broken/empty 与 30 天长度
async def test_settle_summary_filled(db): ...              # P4 summary 的 star_level/streak 非 null
```

- [ ] **Step 2:** 跑确认 FAIL（沙箱外）。
- [ ] **Step 3:** 建模型 → `alembic revision --autogenerate` 人工核对（唯一约束 `(user_id, date)`）→ 双向迁移通过；实现 `progress_service`；`session_service` 懒标记处调 `mark_day_completed + recompute_day`，end 有效处调 `recompute_day`；summary 填扩展字段；`main.py` 注册 router。
- [ ] **Step 4:** `seed.py` 造完 6 天会话后逐日调 `recompute_day + mark_day_completed`（真实路径，不手写 star 行）。
- [ ] **Step 5:** 测试全 PASS + 棘轮 + 全量回归。
- [ ] **Step 6: Commit** `feat(backend): stars and streak with recompute single write path`

### Task 3: 首页星星墙 + 结算星星动画

**Files:**
- Create: `frontend/src/features/progress/StarWall.tsx`、`StreakBadge.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`、`frontend/src/features/settle/SettleSummary.tsx`、`frontend/src/features/focus/MilestoneBanner.tsx`

**Interfaces:**
- Consumes: `GET /api/progress/summary`；P4 SettleSummary 槽位与 summary 扩展字段。
- Produces: HomePage 顶部进度区（P6 在此挂信箱入口）。

- [ ] **Step 1:** `StarWall`：30 天网格，lit 按 level 1/2/3 三档亮度（CSS 变量，不用写死色值散落各处）、dim 灰、broken 空心描边、empty 不渲染；`StreakBadge`：「连续 X 天 · 最长 Y 天」；挂到 HomePage 顶部。
- [ ] **Step 2:** `SettleSummary` 槽位填：星星点亮动画（framer-motion 一次性 scale/opacity，亮度用本场 star_level）+ 连续天数大数字；`was_reset=true` 时文案用「新的一条线，从今天这 5 分钟开始」，否则「明天再来」钩子句。
- [ ] **Step 3:** `MilestoneBanner` 增加小星星图标发光（与 FocusPage 变亮效果同一次触发，不重复动画）。
- [ ] **Step 4:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 5: Commit** `feat(frontend): star wall and settle star animation`

### Task 4: 端到端联调 + 完成门

- [ ] **Step 1:** 三服务同启 + reset seed（小明连续 6 天）+ 演示阈值：首页看到 6 天星墙与「连续 6 天」；完成一场 → 星墙今天点亮、「连续 7 天」，结算页星星动画只播一次。
- [ ] **Step 2:** 全量后端测试 + 棘轮 + lint/build。
- [ ] **Step 3:** 回填 Spec 第 8 节。
- [ ] **Step 4: Commit** `docs: backfill spec 005 results`
