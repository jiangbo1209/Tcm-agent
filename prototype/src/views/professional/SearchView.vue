<template>
  <div class="admin-page search-page">
    <div class="search-layout">
      <aside v-if="searched" class="filter-panel card">
        <div class="filter-panel-head">
          <h2>筛选</h2>
          <button v-if="activeFilterCount" class="filter-clear" type="button" @click="clearFilters">清空</button>
        </div>

        <div class="filter-group">
          <h3>来源类别</h3>
          <label v-for="opt in kindOptions" :key="opt.key" class="filter-option">
            <input
              type="checkbox"
              :checked="kinds.includes(opt.key)"
              @change="toggleKind(opt.key)"
            />
            <span class="opt-label">{{ opt.label }}</span>
            <span class="opt-count">{{ opt.count }}</span>
          </label>
        </div>

        <div class="filter-group">
          <h3>研究类型</h3>
          <label v-for="opt in studyTypeOptions" :key="opt.value" class="filter-option">
            <input
              type="checkbox"
              :checked="filters.studyType === opt.value"
              @change="pickSingle('studyType', opt.value)"
            />
            <span class="opt-label">{{ opt.label }}</span>
            <span class="opt-count">{{ opt.count }}</span>
          </label>
          <p v-if="studyTypeOptions.length === 0" class="filter-empty">暂无选项</p>
        </div>

        <div class="filter-group">
          <h3>证型</h3>
          <label v-for="opt in syndromeOptions" :key="opt.value" class="filter-option">
            <input
              type="checkbox"
              :checked="filters.syndrome === opt.value"
              @change="pickSingle('syndrome', opt.value)"
            />
            <span class="opt-label">{{ opt.label }}</span>
            <span class="opt-count">{{ opt.count }}</span>
          </label>
          <p v-if="syndromeOptions.length === 0" class="filter-empty">暂无选项</p>
        </div>

        <div class="filter-group">
          <h3>年度</h3>
          <label v-for="opt in yearOptions" :key="opt.value" class="filter-option">
            <input
              type="checkbox"
              :checked="filters.year === opt.value"
              @change="pickSingle('year', opt.value)"
            />
            <span class="opt-label">{{ opt.label }}</span>
            <span class="opt-count">{{ opt.count }}</span>
          </label>
        </div>
      </aside>

      <section class="search-main">
        <div class="search-bar card">
          <input
            v-model="keyword"
            class="search-input"
            type="text"
            placeholder="输入关键词、论文标题、证型、方剂…"
            @keydown.enter="search"
          />
          <button class="btn-primary" type="button" @click="search">搜索</button>
        </div>

        <div v-if="searched" class="result-summary">
          共 <strong>{{ results.length }}</strong> 条结果
        </div>

        <div class="result-area">
          <div v-if="!searched" class="empty-state">
            <p class="empty-title">输入关键词检索 DOR 文献与病案</p>
            <p class="empty-desc">支持按题名、作者、证型、方剂、方案等任意字段匹配</p>
          </div>

          <div v-else-if="results.length === 0" class="empty-state">
            <p class="empty-title">未找到匹配记录</p>
            <p class="empty-desc">请调整关键词或左侧筛选条件</p>
          </div>

          <template v-else>
            <article v-for="item in results" :key="item.key" class="card result-card">
              <div class="result-main">
                <div class="result-title-row">
                  <span class="badge" :class="item.kind === 'lit' ? 'badge-teal' : 'badge-warn'">
                    {{ item.kind === "lit" ? "文献" : "病案" }}
                  </span>
                  <span class="result-id">{{ item.id }}</span>
                  <h3 class="result-title">{{ item.title }}</h3>
                </div>
                <div class="result-meta">
                  <span>{{ item.subtitle }}</span>
                  <span v-if="item.tagA">{{ item.kind === "lit" ? "研究类型" : "不孕类型" }}：{{ item.tagA }}</span>
                  <span v-if="item.tagB">证型：{{ item.tagB }}</span>
                  <span class="meta-muted">更新于 {{ item.updatedAt }}</span>
                </div>
                <p class="hit-line">
                  <span class="hit-label">命中</span>
                  <span class="hit-text">{{ item.hitText }}</span>
                </p>
              </div>
              <button class="btn-sm teal" type="button" @click="detail = item">查看详情</button>
            </article>
          </template>
        </div>
      </section>
    </div>

    <div v-if="detail" class="drawer-mask" @click.self="detail = null">
      <aside class="detail-drawer">
        <header class="drawer-head">
          <div>
            <span class="badge" :class="detail.kind === 'lit' ? 'badge-teal' : 'badge-warn'">
              {{ detail.kind === "lit" ? "文献" : "病案" }}
            </span>
            <strong>{{ detail.id }}</strong>
          </div>
          <button class="drawer-close" type="button" @click="detail = null">×</button>
        </header>
        <div class="drawer-body">
          <h2 class="drawer-title">{{ detail.title }}</h2>
          <div v-for="group in detailGroups" :key="group.label" class="drawer-group">
            <h3>{{ group.label }}</h3>
            <dl>
              <template v-for="field in group.fields" :key="field.key">
                <template v-if="detail.values[field.key]">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ detail.values[field.key] }}</dd>
                </template>
              </template>
            </dl>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { LIT_RECORDS, CASE_RECORDS } from "../../data/dorMock";
import { LIT_GROUPS, CASE_GROUPS, flattenGroups } from "../../constants/dorFields";

const keyword = ref("");
const searched = ref(false);
const kinds = ref(["lit", "case"]);
const filters = reactive({ studyType: "", syndrome: "", year: "" });
const detail = ref(null);

function buildRecords() {
  const lit = LIT_RECORDS.map((r) => ({
    key: `lit-${r.id}`,
    id: r.id,
    kind: "lit",
    title: r.values.lit_1 || r.id,
    subtitle: `${r.values.lit_2 || "未知作者"} · ${r.values.lit_3 || "—"}`,
    tagA: r.values.lit_4 || "",
    tagB: r.values.lit_15 || "",
    updatedAt: r.updated_at || "—",
    values: r.values,
  }));
  const cs = CASE_RECORDS.map((r) => ({
    key: `case-${r.id}`,
    id: r.id,
    kind: "case",
    title: `病案 ${r.id}`,
    subtitle: `${r.values.case_1 || "—"} 岁 · ${r.values.case_23 || "未分型"}`,
    tagA: r.values.case_4 || "",
    tagB: r.values.case_23 || "",
    updatedAt: r.updated_at || "—",
    values: r.values,
  }));
  return [...lit, ...cs];
}

const allRecords = buildRecords();

function textOf(rec) {
  return Object.values(rec.values)
    .map((v) => (Array.isArray(v) ? v.join(" ") : String(v ?? "")))
    .join(" ")
    .toLowerCase();
}

const keywordMatches = computed(() => {
  if (!searched.value) return [];
  const words = keyword.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return allRecords;
  return allRecords.filter((rec) => {
    const hay = `${rec.id} ${textOf(rec)}`.toLowerCase();
    return words.every((w) => hay.includes(w));
  });
});

const results = computed(() =>
  keywordMatches.value
    .filter((rec) => kinds.value.includes(rec.kind))
    .filter((rec) => !filters.studyType || rec.tagA === filters.studyType)
    .filter((rec) => !filters.syndrome || rec.tagB === filters.syndrome)
    .filter((rec) => !filters.year || String(rec.values.lit_3 || "") === filters.year)
    .map((rec) => {
      const words = keyword.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
      const hit = Object.entries(rec.values).find(([, v]) => {
        const s = Array.isArray(v) ? v.join(" ") : String(v ?? "");
        return words.some((w) => s.toLowerCase().includes(w));
      });
      return {
        ...rec,
        hitText: hit ? `${hit[0]}：${Array.isArray(hit[1]) ? hit[1].join("、") : hit[1]}`.slice(0, 90) : "标题/编号匹配",
      };
    }),
);

const filterBase = computed(() => keywordMatches.value);
const countBy = (predicate) => filterBase.value.filter(predicate).length;

const kindOptions = computed(() => [
  { key: "lit", label: "文献", count: countBy((r) => r.kind === "lit") },
  { key: "case", label: "病案", count: countBy((r) => r.kind === "case") },
]);

const studyTypeOptions = computed(() => {
  const map = new Map();
  for (const rec of filterBase.value.filter((r) => r.kind === "lit")) {
    if (!rec.tagA) continue;
    map.set(rec.tagA, (map.get(rec.tagA) || 0) + 1);
  }
  return [...map.entries()].map(([value, count]) => ({ value, label: value, count }));
});

const syndromeOptions = computed(() => {
  const map = new Map();
  for (const rec of filterBase.value) {
    if (!rec.tagB) continue;
    map.set(rec.tagB, (map.get(rec.tagB) || 0) + 1);
  }
  return [...map.entries()].map(([value, count]) => ({ value, label: value, count }));
});

const yearOptions = computed(() => {
  const map = new Map();
  for (const rec of filterBase.value) {
    const y = rec.values.lit_3;
    if (!y) continue;
    map.set(String(y), (map.get(String(y)) || 0) + 1);
  }
  return [...map.entries()]
    .sort((a, b) => String(b[0]).localeCompare(String(a[0])))
    .map(([value, count]) => ({ value, label: value, count }));
});

const activeFilterCount = computed(
  () =>
    (kinds.value.length === 2 ? 0 : 1) +
    (filters.studyType ? 1 : 0) +
    (filters.syndrome ? 1 : 0) +
    (filters.year ? 1 : 0),
);

const detailGroups = computed(() => {
  if (!detail.value) return [];
  return (detail.value.kind === "lit" ? LIT_GROUPS : CASE_GROUPS).map((group) => ({
    label: group.label,
    fields: flattenGroups([group]),
  }));
});

function search() {
  searched.value = true;
}

function toggleKind(key) {
  if (kinds.value.includes(key)) {
    if (kinds.value.length === 1) return;
    kinds.value = kinds.value.filter((k) => k !== key);
  } else {
    kinds.value = [...kinds.value, key];
  }
}

function pickSingle(field, value) {
  filters[field] = filters[field] === value ? "" : value;
}

function clearFilters() {
  kinds.value = ["lit", "case"];
  filters.studyType = "";
  filters.syndrome = "";
  filters.year = "";
}
</script>

<style scoped>
.search-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  min-height: calc(100vh - 150px);
}

.filter-panel {
  width: 230px;
  flex-shrink: 0;
  padding: 14px 16px;
  position: sticky;
  top: 0;
}
.filter-panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.filter-panel-head h2 { margin: 0; font-size: 14px; }
.filter-clear { border: none; background: transparent; color: var(--teal); font-size: 11px; cursor: pointer; }
.filter-group { padding: 10px 0; border-top: 1px dashed var(--line); }
.filter-group:first-of-type { border-top: none; }
.filter-group h3 { margin: 0 0 8px; font-size: 12px; color: var(--ink-500); font-weight: 600; }
.filter-option { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; color: var(--ink-700); cursor: pointer; }
.filter-option input { accent-color: var(--teal); }
.opt-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.opt-count { font-size: 10px; color: var(--ink-400); }
.filter-empty { margin: 4px 0; font-size: 11px; color: var(--ink-400); }

.search-main { flex: 1; min-width: 0; display: flex; flex-direction: column; min-height: calc(100vh - 150px); }
.search-bar { display: flex; gap: 10px; padding: 12px 14px; margin-bottom: 10px; }
.search-input { flex: 1; padding: 9px 12px; border: 1px solid #d0d0d0; border-radius: 8px; font-size: 13px; outline: none; }
.search-input:focus { border-color: var(--teal); }
.result-summary { font-size: 12px; color: var(--ink-400); margin-bottom: 8px; }
.result-summary strong { color: var(--teal-dark); }

.result-area { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; color: var(--ink-400); padding: 60px 0; }
.empty-title { margin: 0; font-size: 14px; color: var(--ink-500); }
.empty-desc { margin: 0; font-size: 12px; }

.result-card { display: flex; align-items: flex-start; gap: 14px; padding: 14px 16px; }
.result-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.result-title-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.result-id { font-size: 11px; color: var(--ink-400); font-family: ui-monospace, Consolas, monospace; }
.result-title { margin: 0; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-meta { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11px; color: var(--ink-500); }
.meta-muted { color: var(--ink-400); }
.hit-line { margin: 0; display: flex; gap: 6px; font-size: 11px; color: var(--ink-500); }
.hit-label { flex-shrink: 0; padding: 0 6px; border-radius: 4px; background: #fff7e6; color: #b06a00; }
.hit-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.drawer-mask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); z-index: 80; display: flex; justify-content: flex-end; }
.detail-drawer { width: 560px; max-width: 92vw; height: 100%; background: #fff; display: flex; flex-direction: column; box-shadow: -8px 0 30px rgba(0, 0, 0, 0.15); }
.drawer-head { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--line); }
.drawer-head > div { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.drawer-close { border: none; background: transparent; font-size: 20px; color: var(--ink-400); cursor: pointer; }
.drawer-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.drawer-title { margin: 0 0 14px; font-size: 16px; }
.drawer-group { margin-bottom: 16px; }
.drawer-group h3 { margin: 0 0 8px; font-size: 12px; color: var(--teal-dark); }
.drawer-group dl { margin: 0; display: grid; grid-template-columns: 110px 1fr; gap: 6px 10px; font-size: 12px; }
.drawer-group dt { color: var(--ink-400); }
.drawer-group dd { margin: 0; color: var(--ink-700); word-break: break-all; }
</style>
