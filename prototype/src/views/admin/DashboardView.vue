<template>
  <div class="admin-page">
    <header class="admin-header">
      <div class="header-text">
        <h1>平台总览</h1>
      </div>
      <div class="header-meta">
        <span class="live-dot" aria-hidden="true"></span>
        数据截至 2025-03-19 10:45
      </div>
    </header>

    <!-- 统计卡 -->
    <section class="stat-grid" aria-label="平台核心指标">
      <article
        v-for="s in STATS"
        :key="s.label"
        class="stat-card"
        :class="'tone-' + s.tone"
      >
        <div class="stat-top">
          <span class="stat-label">{{ s.label }}</span>
          <span class="stat-unit">{{ s.unit }}</span>
        </div>
        <p class="stat-value">{{ formatNum(s.value) }}</p>
        <p class="stat-hint">{{ s.hint }}</p>
      </article>
    </section>

    <div class="mid-grid">
      <!-- 最近动态 -->
      <section class="panel activity-panel">
        <div class="panel-head">
          <div class="panel-heading">
            <h2 class="panel-title">最近动态</h2>
          </div>
          <span class="panel-hint">近 24 小时 · {{ ACTIVITIES.length }} 条</span>
        </div>

        <ul class="timeline">
          <li v-for="item in ACTIVITIES" :key="item.time + item.title" class="timeline-item">
            <time class="tl-time">{{ item.time }}</time>
            <span class="tl-rail" aria-hidden="true">
              <span class="tl-node" :class="'tl-' + item.type"></span>
            </span>
            <div class="tl-body">
              <div class="tl-head">
                <strong>{{ item.title }}</strong>
                <span class="tl-actor">{{ item.actor }}</span>
              </div>
              <p class="tl-desc">{{ item.desc }}</p>
            </div>
          </li>
        </ul>
      </section>

      <!-- 待办 -->
      <section class="panel todo-panel">
        <div class="panel-head">
          <div class="panel-heading">
            <h2 class="panel-title">待办</h2>
          </div>
          <span class="todo-total">3 项</span>
        </div>

        <div class="todo-list">
          <router-link
            v-for="todo in TODOS"
            :key="todo.label"
            :to="todo.to"
            class="todo-item"
          >
            <span class="todo-num" :class="'tone-' + todo.tone">{{ todo.count }}</span>
            <span class="todo-main">
              <strong>{{ todo.label }}</strong>
              <small>{{ todo.desc }}</small>
            </span>
            <span class="todo-go">{{ todo.cta }} →</span>
          </router-link>
        </div>

        <div class="todo-foot">
          <router-link to="/admin/tasks">前往标注管理中心 →</router-link>
        </div>
      </section>
    </div>




  </div>
</template>

<script setup>
const STATS = [
  { label: "文献", value: 214, unit: "篇", hint: "64 字段母版 · 已抽取 87%", tone: "teal" },
  { label: "病案", value: 132, unit: "例", hint: "理法方药全链 · 待复核 7", tone: "teal" },
  { label: "标注员", value: 12, unit: "人", hint: "今日在线 7 人", tone: "teal" },
  { label: "待复核", value: 21, unit: "份", hint: "今日新增 5 份", tone: "amber" },
  { label: "图谱节点", value: 1580, unit: "个", hint: "6 类实体 · 孤点率 18.4%", tone: "teal" },
  { label: "图谱边", value: 4312, unit: "条", hint: "7 类关系 · 建图版本 v1.8", tone: "teal" },
];

const TODOS = [
  {
    count: 21,
    label: "条记录待复核",
    desc: "文献 14 · 病案 7",
    tone: "amber",
    cta: "进入复核",
    to: "/admin/data?kind=literature",
  },
  {
    count: 7,
    label: "篇文献抽取失败",
    desc: "版式 / 单位问题，需重抽",
    tone: "red",
    cta: "查看失败",
    to: "/admin/sources/resources",
  },
  {
    count: 3,
    label: "个近似实体待裁决",
    desc: "如「左归丸 / 左归饮」",
    tone: "teal",
    cta: "去裁决",
    to: "/admin/tasks",
  },
];

const ACTIVITIES = [
  {
    time: "10:42",
    type: "pool",
    title: "创建任务池 POOL-2025-018",
    desc: "文献表 · 检索式「补肾填精 AND DOR」· 46 条",
    actor: "黄伟",
  },
  {
    time: "10:15",
    type: "assign",
    title: "派发标注任务 TK-2025-091",
    desc: "指派给周静 · 病案表 25 条 · 截止 03-25",
    actor: "黄伟",
  },
  {
    time: "09:58",
    type: "approve",
    title: "复核通过 LIT-003",
    desc: "证型「痰湿证」变更已合入母版",
    actor: "林舒",
  },
  {
    time: "09:31",
    type: "fail",
    title: "抽取失败 3 篇文献",
    desc: "PDF 版式异常，已进入待复核清单",
    actor: "系统",
  },
  {
    time: "09:02",
    type: "rollback",
    title: "回滚 CASE-002 修改",
    desc: "AMH 0.42 → 0.51 的变更被撤销",
    actor: "黄伟",
  },
  {
    time: "08:47",
    type: "user",
    title: "新增用户 zhoujing",
    desc: "角色：数据标注员 · 状态：启用",
    actor: "黄伟",
  },
];

function formatNum(value) {
  return Number(value).toLocaleString("en-US");
}
</script>

<style scoped>
.admin-page {
  width: 100%;
  min-height: 100%;
  padding: 24px 32px 40px;
  box-sizing: border-box;
}

/* ── 页头 ── */
.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.header-text h1 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-900);
}
.header-sub {
  margin: 0;
  font-size: 12px;
  color: var(--ink-400);
  letter-spacing: 0.2px;
}
.header-meta {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 11px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  font-size: 12px;
  color: var(--ink-500);
  white-space: nowrap;
}
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--teal);
  box-shadow: 0 0 0 3px rgba(0, 121, 107, 0.12);
}

/* ── 统计卡 ── */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  padding: 14px 16px 13px;
  border: 1px solid var(--line);
  border-top: 3px solid var(--teal);
  border-radius: 10px;
  background: var(--card);
  transition: box-shadow 0.18s ease, transform 0.18s ease;
}
.stat-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06);
}
.stat-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
}
.stat-label {
  font-size: 12px;
  color: var(--ink-500);
}
.stat-unit {
  font-size: 11px;
  color: var(--ink-400);
}
.stat-value {
  margin: 7px 0 5px;
  font-size: 26px;
  font-weight: 600;
  line-height: 1.1;
  color: var(--teal);
  font-variant-numeric: tabular-nums;
}
.stat-hint {
  margin: 0;
  font-size: 11px;
  color: var(--ink-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tone-amber {
  border-top-color: var(--warn);
}
.tone-amber .stat-value {
  color: #ef6c00;
}
.tone-red {
  border-top-color: var(--danger);
}
.tone-red .stat-value {
  color: var(--danger);
}

/* ── 面板通用 ── */
.panel {
  padding: 16px 18px 18px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--card);
  margin-bottom: 16px;
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}
.panel-heading {
  min-width: 0;
}
.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-900);
}
.panel-sub {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--ink-400);
}
.panel-hint {
  font-size: 12px;
  color: var(--ink-400);
  white-space: nowrap;
}
.legend-yes {
  color: var(--teal);
  font-weight: 700;
}
.legend-no {
  color: #c7ccd3;
  font-weight: 700;
}
.legend-sep {
  margin: 0 3px;
  color: #dfe3e7;
}

/* ── 中部布局 ── */
.mid-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  align-items: stretch;
}
.mid-grid .panel {
  margin-bottom: 16px;
}

/* ── 能力矩阵 ── */
.matrix-panel {
  min-width: 0;
}
.matrix-wrap {
  overflow-x: auto;
}
.cap-table {
  width: 100%;
  min-width: 560px;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
}
.cap-table th {
  padding: 8px 6px;
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-400);
  text-align: center;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
.cap-table th.role-col {
  text-align: left;
  padding-left: 4px;
}
.cap-table td {
  padding: 9px 6px;
  border-bottom: 1px solid #f0f2f3;
}
.cap-table tbody tr:last-child td {
  border-bottom: none;
}
.cap-table tbody tr:hover {
  background: #f7fbfa;
}
.role-col {
  width: 190px;
}
.role-cell {
  display: flex;
  align-items: center;
  gap: 9px;
}
.role-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.role-info {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
}
.role-info strong {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-900);
}
.role-info small {
  font-size: 10px;
  color: var(--ink-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cap-cell {
  text-align: center;
}
.cap-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
}
.cap-yes {
  background: var(--teal-soft);
  color: var(--teal);
}
.cap-no {
  background: #f5f6f7;
  color: #c7ccd3;
}

/* ── 待办 ── */
.todo-panel {
  display: flex;
  flex-direction: column;
}
.todo-total {
  padding: 2px 9px;
  border-radius: 999px;
  background: #fff8e1;
  color: var(--warn);
  font-size: 11px;
  font-weight: 600;
}
.todo-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}
.todo-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fcfdfd;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.16s ease, background 0.16s ease;
}
.todo-item:hover {
  border-color: var(--teal-border);
  background: #f4faf9;
}
.todo-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  height: 40px;
  border-radius: 9px;
  background: var(--teal-soft);
  color: var(--teal);
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.todo-num.tone-amber {
  background: #fff8e1;
  color: #ef6c00;
}
.todo-num.tone-red {
  background: #ffebee;
  color: var(--danger);
}
.todo-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.todo-main strong {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-900);
}
.todo-main small {
  font-size: 11px;
  color: var(--ink-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.todo-go {
  font-size: 11px;
  color: var(--teal);
  white-space: nowrap;
}
.todo-foot {
  margin-top: 12px;
  padding-top: 11px;
  border-top: 1px dashed var(--line);
  text-align: right;
}
.todo-foot a {
  font-size: 12px;
  color: var(--teal);
  text-decoration: none;
}
.todo-foot a:hover {
  text-decoration: underline;
}

/* ── 数据链路 ── */
.pipeline {
  display: flex;
  align-items: stretch;
}
.flow-step {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px 13px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fbfcfc;
  transition: border-color 0.16s ease, background 0.16s ease;
}
.flow-step:hover {
  border-color: var(--teal-border);
  background: #f4faf9;
}
.flow-end {
  background: linear-gradient(160deg, #00796b, #00695c);
  border-color: var(--teal-dark);
}
.flow-end .flow-index,
.flow-end .flow-tag,
.flow-end .flow-desc {
  color: rgba(255, 255, 255, 0.68);
}
.flow-end .flow-name {
  color: #fff;
}
.flow-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.flow-index {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10px;
  color: var(--ink-400);
}
.flow-tag {
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(0, 121, 107, 0.08);
  color: var(--teal);
  font-size: 9px;
  letter-spacing: 0.3px;
}
.flow-end .flow-tag {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}
.flow-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-900);
  white-space: nowrap;
}
.flow-desc {
  font-size: 10px;
  color: var(--ink-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.flow-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  flex-shrink: 0;
  color: var(--teal-border);
  font-size: 15px;
  font-weight: 700;
}

/* ── 时间线 ── */
.timeline {
  margin: 0;
  padding: 0;
  list-style: none;
}
.timeline-item {
  display: grid;
  grid-template-columns: 46px 22px minmax(0, 1fr);
  gap: 0 10px;
  min-height: 44px;
}
.tl-time {
  padding-top: 2px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  color: var(--ink-400);
  text-align: right;
}
.tl-rail {
  position: relative;
  display: flex;
  justify-content: center;
}
.tl-rail::before {
  content: "";
  position: absolute;
  top: 14px;
  bottom: -2px;
  left: 50%;
  width: 1px;
  background: #e8ecee;
  transform: translateX(-50%);
}
.timeline-item:last-child .tl-rail::before {
  display: none;
}
.tl-node {
  position: relative;
  z-index: 1;
  width: 9px;
  height: 9px;
  margin-top: 5px;
  border: 2px solid #fff;
  border-radius: 50%;
  background: var(--teal);
  box-shadow: 0 0 0 1px var(--teal-border);
}
.tl-pool {
  background: var(--teal);
}
.tl-assign {
  background: #1565c0;
  box-shadow: 0 0 0 1px #bbdefb;
}
.tl-approve {
  background: var(--ok);
  box-shadow: 0 0 0 1px #c8e6c9;
}
.tl-fail {
  background: var(--danger);
  box-shadow: 0 0 0 1px #ffcdd2;
}
.tl-rollback {
  background: var(--warn);
  box-shadow: 0 0 0 1px #ffe0b2;
}
.tl-user {
  background: #6a1b9a;
  box-shadow: 0 0 0 1px #e1bee7;
}
.tl-body {
  padding: 0 0 12px;
  min-width: 0;
}
.timeline-item:last-child .tl-body {
  padding-bottom: 0;
}
.tl-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}
.tl-head strong {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tl-actor {
  flex-shrink: 0;
  font-size: 10px;
  color: var(--ink-400);
  background: #f5f6f7;
  border-radius: 999px;
  padding: 1px 7px;
}
.tl-desc {
  margin: 3px 0 0;
  font-size: 11px;
  color: var(--ink-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 响应式 ── */
@media (max-width: 1240px) {
  .stat-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .mid-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .pipeline {
    flex-wrap: wrap;
    gap: 8px;
  }
  .flow-step {
    flex: 1 1 150px;
  }
  .flow-arrow {
    display: none;
  }
}
@media (max-width: 720px) {
  .admin-page {
    padding: 16px;
  }
  .admin-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .panel {
    padding: 14px;
  }
  .panel-head {
    flex-direction: column;
    gap: 6px;
  }
  .timeline-item {
    grid-template-columns: 40px 18px minmax(0, 1fr);
    gap: 0 8px;
  }
  .tl-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
  }
}
</style>
