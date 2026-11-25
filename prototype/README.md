# TCM-DOR 知识图谱原型（独立）

> 纯前端 Vue 3 原型，**不连接后端**，全部数据为本地 mock。
> 与 `UI/frontend` 完全隔离，不修改现有工程。

## 启动

```bash
cd prototype
npm install
npm run dev      # http://localhost:5600
```

构建：

```bash
npm run build
```

## 四角色

| 角色 | 入口 | 能力 |
|---|---|---|
| 普通用户 | `/chat` | 仅智能问答 |
| 专业用户 | `/chat` `/search` `/graph` | 问答 + 搜索 + 知识图谱 |
| 数据标注员 | `/annotate` | 标注工作台（单一入口） |
| 超级管理员 | `/admin` | 平台总览 / 数据源管理 / ETL管理 / 数据管理 / 标注管理 / 用户管理 |

登录页一键选择角色进入，无需账号密码；侧栏「切换角色」可回到登录页。

## 数据模型

- `src/constants/dorFields.js`：由《文献库母版（精简后）.xlsx》自动生成
  - 文献库 **65 字段 / 8 分组**
  - 病案库 **41 字段 / 8 分组**
  - 必填标记、下拉枚举与 Excel 一致
- `src/data/dorMock.js`：文献/病案各 6 条 DOR 主题 mock 数据

## 页面

```
src/views/
  Login.vue                     角色选择
  chat/ChatView.vue             智能问答（mock 对话）
  professional/SearchView.vue   智能搜索（文献+病案）
  professional/GraphView.vue    知识图谱（SVG 实体关系图）
  annotator/WorkbenchView.vue   标注工作台（文献/病案分栏 + 原文对照）
  admin/DashboardView.vue       平台总览
  admin/DataManageView.vue      数据管理（文献库/病案库同页切换）
  admin/LiteratureLibrary.vue   文献库（65 字段，人工编辑）
  admin/CaseLibrary.vue         病案库（41 字段，人工编辑）
  admin/DataSourceView.vue      数据源管理（上传/队列均为弹窗，上限 10）
  admin/UsersView.vue           用户与权限
  admin/AnnotationTasksView.vue 标注任务（任务池/复核/操作记录）
  admin/etl/                    ETL管理（资源管理 / 质检看板 / 基础配置）
```

## 说明

- 无 axios、无 API 请求、无鉴权后端；角色状态仅存 localStorage
- 字段规模与分组取自甲方需求 Excel，界面用于评审信息架构与交互

## 本轮交互要点

- **数据管理**：文献库/病案库同一页面，顶部菜单切换；编辑为左右分栏（左原文、右字段），不含 AI 重抽按钮。
- **数据源管理**：主列表管理已上传文件；「上传文件」「上传队列」均为弹窗，队列最多 10 个，逐文件设置「文献 / 病案」。
- **ETL管理**：必须先选执行范围（未抽取 / 指定记录 / 按筛选条件），不允许默认全量；与质检看板合并为同页两个菜单。
- **标注工作台**：文献 / 病案分别标注；三栏布局（任务列表 | 原文 | 字段表单）。

## ETL 状态流

```
待抽取 → 抽取中 → 待校验 → 待入图 → 已完成
                ↘ 抽取失败 →（重试）抽取中
待校验 →（退回）待抽取；待入图 →（退回）待校验；已完成 →（重抽）待抽取
```

- 每个状态一个页面，页面内提供该状态的专属批量操作
- 抽取结果支持原文对照、字段级置信度、问题面板与历史版本
- 抽取任务向导：对象 → 范围（未抽取/指定/筛选）→ 确认

## 标注任务统一模型

- ETL 抽取完成（review）→ 管理员在「标注管理」勾选资源下发任务
- 标注员在工作台标注/校验 → 提交 → 管理员复核
- 复核通过 → 文档直接入图（graphed）；驳回 → 该标注员「返工箱」
- 抽取校验不再单独存在，统一为标注任务的一种来源
