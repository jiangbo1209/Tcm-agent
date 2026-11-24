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
| 超级管理员 | `/admin` | 总览 / 文献库 / 病案库 / 用户与权限 / 标注任务 / ETL 质检 |

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
  annotator/WorkbenchView.vue   标注工作台
  admin/DashboardView.vue       平台总览
  admin/LiteratureLibrary.vue   文献库（65 字段）
  admin/CaseLibrary.vue         病案库（41 字段）
  admin/UsersView.vue           用户与权限
  admin/AnnotationTasksView.vue 标注任务（任务池/复核/操作记录）
  admin/EtlQualityView.vue      ETL 抽取质检看板
```

## 说明

- 无 axios、无 API 请求、无鉴权后端；角色状态仅存 localStorage
- 字段规模与分组取自甲方需求 Excel，界面用于评审信息架构与交互
