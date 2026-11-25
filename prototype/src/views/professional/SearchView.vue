<template>
  <div class="admin-page">
    <div class="admin-header">
      <div class="header-text">
        <h1>智能搜索</h1>
      </div>
    </div>

    <div class="card search-panel">
      <div class="search-row">
        <input
          v-model="keyword"
          class="filter-input keyword-input"
          type="text"
          placeholder="输入关键词，如：肾虚证、AMH、左归丸…"
          @keydown.enter="search"
        />
        <button class="btn-primary" @click="search">搜索</button>
      </div>

      <div class="filter-row">
        <div class="filter-group">
          <span class="filter-label">数据类型</span>
          <label
            v-for="opt in typeOptions"
            :key="opt.key"
            class="check-item"
            :class="{ checked: kinds.includes(opt.key) }"
          >
            <input
              type="checkbox"
              :checked="kinds.includes(opt.key)"
              @change="toggleKind(opt.key)"
            />
            {{ opt.label }}
          </label>
        </div>

        <div class="filter-group">
          <span class="filter-label">研究类型</span>
          <select v-model="studyType" class="filter-select">
            <option value="">全部</option>
            <option v-for="opt in studyTypeOptions" :key="opt" :value="opt">
              {{ opt }}
            </option>
          </select>
          <span class="filter-note">仅作用于文献</span>
        </div>

        <span v-if="searched" class="result-count">共 {{ results.length }} 条结果</span>
      </div>
    </div>

    <div class="result-area">
      <div v-if="!searched" class="empty-state">
        <div class="empty-icon">🔍</div>
        <p class="empty-title">输入关键词检索 DOR 文献与病案</p>
        <p class="empty-desc">支持按题名、作者、证型、方剂、方案等任意字段匹配，可组合多个关键词</p>
      </div>

      <div v-else-if="!results.length" class="empty-state">
        <div class="empty-icon">🗂️</div>
        <p class="empty-title">
          {{ kinds.length ? "未找到匹配记录" : "请至少选择一种数据类型" }}
        </p>
        <p v-if="kinds.length" class="empty-desc">试试更换关键词，或放宽研究类型筛选</p>
      </div>

      <template v-else>
        <article
          v-for="item in results"
          :key="item.key"
          class="card result-card"
        >
          <div class="result-main">
            <div class="result-title-row">
              <span
                class="badge"
                :class="item.kind === 'lit' ? 'badge-teal' : 'badge-ok'"
              >
                {{ item.kind === "lit" ? "文献" : "病案" }}
              </span>
              <span class="result-id">{{ item.record.id }}</span>
              <h3 class="result-title">{{ item.title }}</h3>
            </div>

            <div class="result-meta">
              <span>{{ item.subtitle }}</span>
              <span v-if="item.tagA" class="meta-item">
                {{ item.kind === "lit" ? "研究类型" : "不孕类型" }}：{{ item.tagA }}
              </span>
              <span v-if="item.tagB" class="meta-item">证型：{{ item.tagB }}</span>
              <span class="meta-item">
                置信度：
                <b :class="confClass(item.record.confidence)">
                  {{ formatPct(item.record.confidence) }}
                </b>
              </span>
              <span class="meta-item meta-muted">更新于 {{ item.record.updated_at }}</span>
            </div>

            <p class="hit-line">
              <span class="hit-label">命中</span>
              <span class="hit-text">{{ item.hitText }}</span>
              <span v-if="item.hits.length > 1" class="hit-more">
                等 {{ item.hits.length }} 处匹配
              </span>
            </p>
          </div>

          <div class="result-actions">
            <button class="btn-sm teal" @click="openDetail(item)">查看详情</button>
          </div>
        </article>
      </template>
    </div>

    <transition name="drawer">
      <div v-if="detail" class="drawer-mask" @click.self="detail = null">
        <aside class="drawer">
          <header class="drawer-head">
            <div>
              <div class="drawer-head-top">
                <span
                  class="badge"
                  :class="detail.kind === 'lit' ? 'badge-teal' : 'badge-ok'"
                >
                  {{ detail.kind === "lit" ? "文献" : "病案" }}
                </span>
                <span class="result-id">{{ detail.record.id }}</span>
                <span
                  class="badge"
                  :class="statusMeta(detail.record.status).cls"
                >
                  {{ statusMeta(detail.record.status).label }}
                </span>
              </div>
              <h2 class="drawer-title">{{ detail.title }}</h2>
              <p class="drawer-sub">
                置信度 {{ formatPct(detail.record.confidence) }} · 更新于
                {{ detail.record.updated_at }} · 共 {{ detailFieldCount }} 个字段有值
              </p>
            </div>
            <button class="drawer-close" @click="detail = null">×</button>
          </header>

          <div class="drawer-body">
            <section
              v-for="group in detailGroups"
              :key="group.label"
              class="detail-group"
            >
              <h4 class="group-title">{{ group.label }}</h4>
              <dl class="kv-list">
                <template v-for="row in group.rows" :key="row.key">
                  <dt
                    class="kv-key"
                    :class="{ 'kv-hit': detail.hitKeys.includes(row.key) }"
                  >
                    {{ row.label }}
                  </dt>
                  <dd
                    class="kv-value"
                    :class="{ 'kv-hit': detail.hitKeys.includes(row.key) }"
                  >
                    {{ row.value }}
                  </dd>
                </template>
              </dl>
            </section>
          </div>
        </aside>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import {
  LIT_RECORDS,
  CASE_RECORDS,
  DOR_STATUS_META,
} from "../../data/dorMock";
import {
  LIT_GROUPS,
  CASE_GROUPS,
  flattenGroups,
} from "../../constants/dorFields";

const litLabelMap = Object.fromEntries(
  flattenGroups(LIT_GROUPS).map((f) => [f.key, f.label]),
);
const caseLabelMap = Object.fromEntries(
  flattenGroups(CASE_GROUPS).map((f) => [f.key, f.label]),
);

const INDEX = [
  ...LIT_RECORDS.map((record) => ({ kind: "lit", record })),
  ...CASE_RECORDS.map((record) => ({ kind: "case", record })),
];

const typeOptions = [
  { key: "lit", label: "文献" },
  { key: "case", label: "病案" },
];

const studyTypeOptions = [...new Set(
  LIT_RECORDS.map((r) => r.values.lit_4).filter(Boolean),
)];

const keyword = ref("");
const kinds = ref(["lit", "case"]);
const studyType = ref("");
const searched = ref(false);
const applied = ref({ tokens: [], kinds: [], studyType: "" });
const detail = ref(null);

function toggleKind(key) {
  if (kinds.value.includes(key)) {
    kinds.value = kinds.value.filter((k) => k !== key);
  } else {
    kinds.value = [...kinds.value, key];
  }
}

function search() {
  applied.value = {
    tokens: keyword.value.trim().toLowerCase().split(/\s+/).filter(Boolean),
    kinds: [...kinds.value],
    studyType: studyType.value,
  };
  searched.value = true;
}

function truncate(text, len) {
  const s = String(text);
  return s.length > len ? `${s.slice(0, len)}…` : s;
}

function formatPct(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function confClass(value) {
  const n = Number(value) || 0;
  if (n >= 0.85) return "conf-high";
  if (n >= 0.6) return "conf-mid";
  return "conf-low";
}

function statusMeta(status) {
  return DOR_STATUS_META[status] || { label: status || "—", cls: "badge-muted" };
}

function buildMeta(entry) {
  const v = entry.record.values;
  if (entry.kind === "lit") {
    return {
      title: v.lit_1 || "（无题名）",
      subtitle: `${v.lit_2 || "—"} · ${v.lit_3 || "—"} 年`,
      tagA: v.lit_4 || "",
      tagB: v.lit_15 || "",
    };
  }
  return {
    title: `病案 ${entry.record.id}`,
    subtitle: `${v.case_1 || "—"} 岁 · ${v.case_4 || "—"}`,
    tagA: v.case_4 || "",
    tagB: v.case_23 || "",
  };
}

const results = computed(() => {
  if (!searched.value) return [];
  const { tokens, kinds: activeKinds, studyType: activeStudyType } =
    applied.value;
  if (!activeKinds.length) return [];

  const out = [];
  for (const entry of INDEX) {
    if (!activeKinds.includes(entry.kind)) continue;
    if (
      activeStudyType &&
      (entry.kind !== "lit" || entry.record.values.lit_4 !== activeStudyType)
    ) {
      continue;
    }

    const values = entry.record.values;
    const corpus = `${entry.record.id} ${Object.values(values).join(" ")}`.toLowerCase();
    if (tokens.length && !tokens.every((t) => corpus.includes(t))) continue;

    const labelMap = entry.kind === "lit" ? litLabelMap : caseLabelMap;
    const hits = [];
    if (tokens.length) {
      for (const [key, val] of Object.entries(values)) {
        if (val === undefined || val === null || val === "") continue;
        const text = String(val);
        if (tokens.some((t) => text.toLowerCase().includes(t))) {
          hits.push({ key, label: labelMap[key] || key, value: text });
        }
      }
    }

    let hitText = "未输入关键词，浏览全部记录";
    if (hits.length) {
      hitText = `${hits[0].label}：${truncate(hits[0].value, 60)}`;
    } else if (tokens.length) {
      hitText = "匹配记录（编号命中，未定位具体字段）";
    }

    out.push({
      key: `${entry.kind}-${entry.record.id}`,
      kind: entry.kind,
      record: entry.record,
      hits,
      hitText,
      ...buildMeta(entry),
    });
  }
  return out;
});

function openDetail(item) {
  detail.value = {
    ...item,
    hitKeys: item.hits.map((h) => h.key),
  };
}

const detailGroups = computed(() => {
  const item = detail.value;
  if (!item) return [];
  const values = item.record.values;
  const groups = item.kind === "lit" ? LIT_GROUPS : CASE_GROUPS;
  const known = new Set();
  const out = [];

  for (const group of groups) {
    const rows = [];
    for (const field of group.fields) {
      const val = values[field.key];
      if (val === undefined || val === null || val === "") continue;
      known.add(field.key);
      rows.push({ key: field.key, label: field.label, value: String(val) });
    }
    if (rows.length) out.push({ label: group.label, rows });
  }

  const extras = Object.entries(values)
    .filter(
      ([key, val]) =>
        !known.has(key) && val !== undefined && val !== null && val !== "",
    )
    .map(([key, val]) => ({ key, label: key, value: String(val) }));
  if (extras.length) out.push({ label: "其他字段", rows: extras });

  return out;
});

const detailFieldCount = computed(() =>
  detailGroups.value.reduce((n, g) => n + g.rows.length, 0),
);
</script>

<style scoped>
.header-text h1 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-900);
}

.search-panel {
  padding: 16px 18px;
  margin-bottom: 16px;
}

.search-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.keyword-input {
  flex: 1;
  width: auto;
  padding: 9px 12px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 20px;
  margin-top: 14px;
  padding-top: 13px;
  border-top: 1px dashed var(--line);
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 9px;
}

.filter-label {
  font-size: 12px;
  color: var(--ink-500);
}

.filter-note {
  font-size: 11px;
  color: var(--ink-400);
}

.check-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 11px;
  border: 1px solid #d0d0d0;
  border-radius: 14px;
  font-size: 12px;
  color: var(--ink-700);
  background: #fff;
  cursor: pointer;
  user-select: none;
  transition: all 0.15s ease;
}

.check-item input {
  display: none;
}

.check-item.checked {
  border-color: var(--teal);
  background: var(--teal-soft);
  color: var(--teal-dark);
}

.result-count {
  margin-left: auto;
  font-size: 12px;
  color: var(--ink-500);
}

.result-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 15px 18px;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}

.result-card:hover {
  border-color: var(--teal-border);
  box-shadow: 0 2px 10px rgba(0, 121, 107, 0.08);
}

.result-main {
  flex: 1;
  min-width: 0;
}

.result-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.result-id {
  font-size: 12px;
  color: var(--ink-400);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.result-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-900);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 7px;
  font-size: 12px;
  color: var(--ink-500);
}

.meta-muted {
  color: var(--ink-400);
}

.conf-high {
  color: var(--ok);
}

.conf-mid {
  color: var(--warn);
}

.conf-low {
  color: var(--danger);
}

.hit-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 9px 0 0;
  padding: 7px 10px;
  background: #f6fbfa;
  border-left: 3px solid var(--teal-border);
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.6;
}

.hit-label {
  flex: 0 0 auto;
  padding: 0 6px;
  border-radius: 3px;
  background: var(--teal-soft);
  color: var(--teal-dark);
  font-size: 11px;
}

.hit-text {
  color: var(--ink-700);
  word-break: break-word;
}

.hit-more {
  color: var(--ink-400);
  white-space: nowrap;
}

.result-actions {
  flex: 0 0 auto;
}

.empty-state {
  padding: 76px 20px;
  text-align: center;
  color: var(--ink-400);
  background: #fff;
  border: 1px dashed var(--line);
  border-radius: 10px;
}

.empty-icon {
  font-size: 30px;
  margin-bottom: 12px;
}

.empty-title {
  margin: 0 0 6px;
  font-size: 14px;
  color: var(--ink-500);
}

.empty-desc {
  margin: 0;
  font-size: 12px;
  color: var(--ink-400);
}

.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(26, 26, 46, 0.32);
  z-index: 60;
  display: flex;
  justify-content: flex-end;
}

.drawer {
  width: 480px;
  max-width: 92vw;
  height: 100%;
  background: #fff;
  display: flex;
  flex-direction: column;
  box-shadow: -6px 0 24px rgba(0, 0, 0, 0.12);
}

.drawer-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--line);
  background: #fafcfc;
}

.drawer-head-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.drawer-title {
  margin: 0 0 6px;
  font-size: 15px;
  line-height: 1.55;
  color: var(--ink-900);
}

.drawer-sub {
  margin: 0;
  font-size: 11px;
  color: var(--ink-400);
}

.drawer-close {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  color: var(--ink-500);
  font-size: 17px;
  line-height: 1;
  cursor: pointer;
}

.drawer-close:hover {
  border-color: var(--teal);
  color: var(--teal);
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 28px;
}

.detail-group {
  margin-bottom: 18px;
}

.group-title {
  margin: 0 0 8px;
  padding-left: 8px;
  border-left: 3px solid var(--teal);
  font-size: 13px;
  font-weight: 600;
  color: var(--teal-dark);
}

.kv-list {
  display: grid;
  grid-template-columns: 116px 1fr;
  gap: 1px;
  margin: 0;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}

.kv-key,
.kv-value {
  margin: 0;
  padding: 8px 10px;
  background: #fff;
  font-size: 12px;
  line-height: 1.65;
}

.kv-key {
  color: var(--ink-500);
  background: #fafafa;
}

.kv-value {
  color: var(--ink-700);
  word-break: break-word;
}

.kv-hit {
  background: #f1faf8 !important;
  color: var(--teal-dark) !important;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.2s ease;
}

.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: transform 0.24s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(100%);
}

@media (max-width: 780px) {
  .result-card {
    flex-direction: column;
    align-items: flex-start;
  }

  .result-actions {
    align-self: flex-end;
  }
}
</style>
