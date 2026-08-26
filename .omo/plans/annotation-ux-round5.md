# annotation-ux-round5 — 复核队列前端修复 + 高亮语义 + 操作记录分类 + 标注记录入侧栏

> 状态：**草稿待批准**。批准后按 `task()` 编排执行。
> 基线：pytest `225 passed / 2 skipped / 1 allowed flaky`（`test_pg_concurrent_claims_exactly_one_winner`）；`npm run build` EXIT=0。

## 需求溯源（用户 8 点）

| 编号 | 需求 | 诊断结论（已核） |
|---|---|---|
| 1a | 复核队列前端有问题 | Round-4 分组重构后模板更新但 `<style scoped>` 仍为「平铺分页」旧样式，`review-group-*`/`review-detail-*`/`review-expand-*`/`diff-*` 零样式 |
| 1b | 点开复核任务内项目自动展开 | 现为单值 `expandedReviewId`，进入详情需逐行点「展开」且只能展开一行 |
| 1c | ■ 高亮=标注员修改字段 | **不改**（用户明示 skip） |
| 1d | 操作记录分类三组 | `LOG_ACTIONS` 10 动作扁平，需分 任务记录/修改记录/复核记录 |
| 1e | 复核任务内前端也不对 | 同 1a 根因（diff 网格/展开行/详情页无样式） |
| 2a | 标注记录放 sidebar | 现为工作台内抽屉；annotator 侧栏仅 `/annotate` 一项 |
| 2b | 无需修改全字段`--`被高亮 + 是否真提交`--` | **纯前端**：`diffFields` 取 current 全字段，`formatValue(undefined)=“—”`≠当前值→全高亮。后端已正确（`approve_submission` 空差异快速通道不触核心表） |
| +1 | 向导预览 v-if+v-for 同元素 | Vue 3 下 `item` 未定义，真 bug，L128-131 |

## 关键决策（已定）

1. **1b 自动展开**：`expandedReviewId` 标量 → `expandedReviewIds: Set`；`openReviewDetail` 时全量展开；详情工具栏加「全部展开/收起」；`loadReviewGroups` 刷新裁剪同步改 Set。
2. **1d 分类映射**：
   - 任务记录：`claim`(领取)、`assign`(代派)、`submit`(提交)、`expire`(过期)
   - 修改记录：`draft`(草稿)、`no_change`(无变更)、`save_direct`(直改)、`rollback`(回滚)
   - 复核记录：`approve`(通过)、`reject`(驳回)
3. **2b 高亮修复**：`diffFields` 只返回 `Object.keys(proposed_fields)`；空 `proposed_fields` 时展开区渲染「无需修改」占位（不渲染 diff 网格）；`diff-changed` 仅对真出现在 `proposed_fields` 且值有差异的字段生效。后端加测试锁定「空 proposed 审批不改核心表」。
4. **2a sidebar**：新增 annotator 导航项「标注记录」→ 路由 `/annotate/history`；放宽 router 守卫（`/annotate` 前缀放行）；工作台抽屉改为跳转该页。
5. **不引入新依赖**；不改根 `Settings` 扁平字段；`.env.example` 不新增键。

## TODOs

- [x] 1. 复核队列/详情/diff 缺失样式补全（1a+1e，HEAVY）— 为 `.review-group-list/-card/-info/-task/-annotator/-table/-count/-time`、`.review-detail-header/-title/-time`、`.review-flat-list`、`.review-expand-row/-cell`、`.diff-grid/-col/-col-title/-row/-key/-val/-legend/-legend-mark`、`.review-count`、`.review-select-all`、`.rev-summary`、`.badge-no-diff`、`.badge-has-diff`、`.core-missing-badge` 补 scoped 样式；复用已有 `.review-toolbar/.review-table/.review-row/.row-selected/.row-core-missing/.diff-changed`；`npm run build` EXIT=0；截图复核队列+详情两态
- [x] 2. 进入复核自动展开 + 多行展开改造（1b）— `expandedReviewId`→`expandedReviewIds:Set`；`openReviewDetail` 全量展开；详情工具栏「全部展开/收起」；`loadReviewGroups` 刷新裁剪改 Set 语义；`npm run build` EXIT=0；Playwright 断言进入详情即见展开 diff
- [x] 3. 操作记录三分类（1d）— `ACTION_CATEGORIES` 三段映射 + 分类筛选下拉（全部/任务记录/修改记录/复核记录）与现有 action 筛选并存 + 分类列/徽章；测试断言 10 动作均落唯一分类
- [x] 4. 标注记录移入 sidebar（2a）— Sidebar annotator 块增「标注记录」项 → `/annotate/history`；新增只读历史视图（复用 `myAnnotationHistory`）；路由守卫放行 `/annotate` 前缀；工作台「我的标注」改为跳转
- [x] 5. 修复无需修改全字段高亮 + 空 proposed 审批不落库锁测试（2b，HEAVY）— 前端 `diffFields` 只返回 proposed 键、空 proposed 渲染「无需修改」占位、`diff-changed` 仅针对 proposed 内的真差异字段；后端新增测试锁定空 proposed 审批不改核心表（`approve_submission` L1572 fast-path）
- [x] 6. 向导预览 v-if+v-for 同元素修正 — L128-131 拆 `<template v-for>` + 内层 `v-if`；`npm run build` EXIT=0

## Final Verification Wave

- [x] F1. 计划合规审计（explore）— 逐条核对 6 任务+5 决策+Must-NOT-Have（无新依赖/不改 Settings/.env.example）；输出 `.omo/evidence/r5-F1.md`，末行 `VERDICT`
- [x] F2. 代码质量评审（oracle）— 缺失样式补全的类名契约、Set 展开的刷新裁剪一致性、分类映射的互斥完备、`diffFields` 语义回归、空 proposed 锁测试充分性；`.omo/evidence/r5-F2.md`
- [x] F3. 真实手工 QA（Sisyphus-Junior+Playwright）— 起栈：①复核队列样式实装 ②进入详情即全展开 ③操作记录三分类筛选 ④标注员侧栏「标注记录」入口可访问 ⑤无需修改条目展开显示占位非全`--`高亮 ⑥构建预览不崩溃（v-if/v-for）；截图 `.omo/evidence/r5-F3/`
- [x] F4. 回归审计 — pytest 全量基线（225/2/1）+ `npm run build` 严格退出码 + grep 终检 + `git status` 干净 + `git ls-files .omo` 空；`.omo/evidence/r5-F4.md`

## 环境事实（沿袭 round-4）

- python=`/home/huiguo/miniforge3/envs/tools/bin/python`；pytest 从 `UI/backend`；基线唯一允许 flaky `test_pg_concurrent_claims_exactly_one_winner`
- docker PG `docker-compose up -d postgresql`，creds `127.0.0.1:5432/postgres/Tcm@2026_pg/papers_records`；QA 后必须 `docker-compose stop postgresql`
- QA 禁 Windows 互操作/杀外部进程/泛杀；端口冲突只换端口（8012/5501）；后端 `ANNOTATION_ENABLED=true` 起栈
- 后台 worker 会话静默死亡高发，证据 `.omo/evidence/` 落盘为准；终验审计遇死亡改由 root 亲自执行