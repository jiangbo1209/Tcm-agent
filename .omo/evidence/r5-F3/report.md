# R5-F3 手工 QA 报告

- 日期: 2026-08-26
- 栈: docker PG up, backend ANNOTATION_ENABLED=true uvicorn 8011, frontend vite 5500
- 账号: admin1/Aa123456 (admin), annot1/Aa123456 (annotator)
- 构建: vite build EXIT 0 (AnnotationManagement-Co0nj5Rv.js 36.20kB, 13.59s)
- PG: 127.0.0.1:5432/postgres/Tcm@2026_pg/papers_records — tcm-postgresql Up
- 前端: http://127.0.0.1:5500 (Vite 5.4.21), 后端: http://127.0.0.1:8011 (uvicorn)
- 证据目录: .omo/evidence/r5-F3/

| Flow | 标题 | 预期 | 结果 | 截图 |
|------|------|------|------|------|
| 1 | 复核队列样式实装 | 分组卡片带阴影/圆角/hover，任务信息分项展示 | PASS | flow1.png |
| 2 | 进入详情即全展开 | 点击进入后所有条目自动展开 diff，无需手动点展开 | PASS | flow2.png |
| 3 | 操作记录三分类筛选 | 分类下拉含3类+表头分类列+徽章，前端过滤生效 | PASS | flow3.png |
| 4 | 标注员侧栏「标注记录」入口 | 侧栏可见标注记录链接，/annotate/history 可访问且不重定向 | PASS | flow4.png |
| 5 | 无需修改占位非全`--`高亮 | 空 proposed 显示“无需修改”占位，无 diff-changed 高亮 | PASS | flow5.png |
| 6 | 构建预览不崩溃（v-if/v-for） | 预览候选明细表正常渲染，无 v-if/v-for 报错 | PASS | flow6.png |

**VERDICT: APPROVE (6/6 flows PASS)**

---

## 详情

### Flow 1 — 复核队列样式实装 (T1)
- 定位: [data-testid="review-group-list"] + .review-group-card
- 结果: cards=1 visible=True styled=True shadow=True bg=rgb(255,255,255) task=True annotator=True
- 卡片: box 1116x55, border #e0e0e0 radius 10px shadow 0 2px 8px rgba(0,0,0,0.06), hover 0 4px 14px
- 子项: .review-group-task (#00796b 14px) / .review-group-annotator (#333) / .review-group-table (teal badge) / .review-group-count / .review-group-time
- 截图: flow1.png — 任务 #9 · annot1 · 文献元数据 · 13 条待复核，卡片独立阴影

### Flow 2 — 进入详情即全展开 (T2)
- 操作: 复核队列点击「进入复核」→ 自动进入任务详情页
- 结果: header=True rows=13 expanded=13 diffGrids=9 placeholders=4 toggle=全部收起
- 验证: expandedReviewIds=Set(group.items.map(sid)) 全量初始化, isAllExpanded=True, toggleAllExpand 正常
- 展开行: .review-expand-row 13 行无需手动点击即全部展开，diff-grid 与 placeholder 并存
- 截图: flow2.png — 详情全展开，工具栏显示“全部收起”

### Flow 3 — 操作记录三分类筛选 (T3)
- 定位: 操作记录 tab → 筛选栏 3 个 select + 记录ID输入
- 下拉1: 全部表/文献/病案/指南 (4 选项)
- 下拉2 (分类): 全部分类/任务记录/修改记录/复核记录 (4 选项) — ACTION_CATEGORIES 映射 4+4+2
- 下拉3 (动作): filteredLogActions 随分类动态收窄 (任务记录→claim,assign,submit,expire 等)
- 表头: 分类列存在 (th:has-text("分类"))，每行 badge-category-task/edit/review 正确着色
- 过滤验证: 任务记录 rows=2 badges=2, 修改记录 rows=7 badges=7, 复核记录 rows=11 badges=11
- 截图: flow3.png — 操作记录页分类筛选与徽章

### Flow 4 — 标注员侧栏「标注记录」入口 (T4)
- 账号: annot1 (role=annotator) 登录后侧栏检查
- 侧栏: 标注工作台 (href=/annotate active exact) + 标注记录 (href=/annotate/history) 双链接均可见
- 点击跳转: /annotate/history → 200, 表格可见 title="标注记录", rows=20, 不被 guard 重定向回 /annotate
- 直达: GET /annotate/history 同样可访问 (startsWith guard 已放行)
- 路由: router/index.js 新增 annotate/history 懒加载 AnnotationHistoryView.vue, Sidebar.vue clock 图标
- 截图: flow4.png — annot1 侧栏双入口 + history 表格 (flow4b.png 为直达验证冗余)

### Flow 5 — 无需修改占位非全`--`高亮 (T5)
- 定位: 详情页空 proposed (proposed_fields={}) 的条目
- 占位: .no-diff-placeholder 4 处, text=无需修改 visible=True color=rgb(153,153,153) align=center padding 18px
- 隔离: placeholder 行内 hasRow=4 diffInPh=0 changedInPh=0 — 无 diff-grid / diff-changed 误高亮
- 徽章: badge-no-diff 对应“无需修改”汇总列, diffFields 仅 Object.keys(proposed) (空返回 [])
- 后端: approve空差异仅写 submission/item/log 不触核心表 (test_annotation_2b_highlight 2用例 PASS)
- 截图: flow5.png — 无需修改占位居中灰色文字，无高亮块

### Flow 6 — 构建预览不崩溃（v-if/v-for） (T6)
- 操作: 任务池 → 新建任务 → 预览 (POST /api/annotation/admin/pools/preview)
- 结果: previewVisible=True wizPreview=True rows=17 eligible=17 text=命中 37 条，可入池 17 条（另有 20 条已被占用或已完成标注） still=True hasError=0
- 修复: `<template v-for>` 包裹 `<tr v-if="eligible">` 替代同元素 v-for+v-if, :key 移至 template
- 表格: .wiz-preview-table .wiz-row 17 行 .badge-eligible 17, 分页 1/2 页正常
- 构建: npm run build EXIT 0, 无 console error, 无 vite-error-overlay
- 截图: flow6.png — 建池向导预览表正常渲染

---

## 证据

- .omo/evidence/r5-F3/flow1.png (39K) — 复核队列卡片样式
- .omo/evidence/r5-F3/flow2.png (123K) — 详情全展开
- .omo/evidence/r5-F3/flow3.png (190K) — 操作记录三分类
- .omo/evidence/r5-F3/flow4.png (144K) — 标注记录侧栏+历史页
- .omo/evidence/r5-F3/flow5.png (123K) — 无需修改占位
- .omo/evidence/r5-F3/flow6.png (114K) — 向导预览
- 冗余: flow4b.png (同 flow4 直达验证)

## 清理

- 杀 PID: backend 224702, frontend 224980 (opencode 自身 PID 不碰)
- docker-compose stop postgresql (容器 tcm-postgresql)
- No wsl/shutdown/pkill
