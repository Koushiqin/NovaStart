---
name: implement-change
description: 实现一个需求或代码改动时使用。从需求澄清到写 Spec 再到编码的完整流程。
---

# 变更实施

## 何时使用

任何功能开发、行为修改、结构性重构。纯 typo / 单行修复可跳过 Spec，但仍须遵守边界。

## 使用前必读

1. `AGENTS.md`（硬边界与协作规则）
2. `docs/dev-order.md`（强制：六步垂直切片顺序 + 功能先后顺序，不得插队）
3. `docs/architecture.md`（分层与数据 owner）
4. 相关需求来源：`brainstorming.md` 对应条目

## 步骤

1. **澄清**：验收条件不清楚时，先向用户提问，不猜。范围确认后持续执行，不反复请求批准。
2. **写 Spec**：复制 `docs/spec-template.md` 到 `docs/specs/NNN-标题.md`，填 1–7 节。结构性变更先回答模板末尾五问（哪一层 / owner 在哪 / 是否重复状态 / 是否影响接口 / 哪些检查须通过）。
3. **实现**：
   - 后端：严格 `routers → services → models`；时间只走 `Clock`；幂等 / 并发用 DB 约束与行锁，不在内存造状态。
   - 前端：HTTP 走 `api/client.ts`，时间走 `useServerClock`，全局状态只进 `store/app.ts`。
   - 改模型必配 Alembic 迁移并人工核对 autogenerate 结果。
4. **自测**：按 Spec 第 7 节跑命令（见 run-tests Skill）。
5. **Review**：按 review Skill 对照 Spec 验收。
6. **回填**：Spec 第 8 节写执行结果与未验证项。

## 禁止

- 新增平行写入路径 / 重复状态；绕过已有 owner 模块。
- 为「不够完整」的模块擅自扩大范围。
- 破坏性变更、新增依赖、改检查语义前未说明并确认。
- 提交真实密钥；`git add` 未跟踪的 TECH_STACK.md / techstack_plan.md。

## 完成判定

Spec 验收条件逐条有证据（命令输出 / 测试通过），第 8 节已回填。
