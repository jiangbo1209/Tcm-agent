<template>
  <div class="admin-page">
    <div class="mgmt-tabs" role="tablist" aria-label="数据管理视图">
      <button
        v-for="tab in TABS"
        :key="tab.key"
        class="mgmt-tab"
        :class="{ active: activeKind === tab.key }"
        type="button"
        role="tab"
        :aria-selected="activeKind === tab.key"
        @click="setKind(tab.key)"
      >
        {{ tab.label }}
        <span class="mgmt-count">{{ tab.count }}</span>
      </button>
    </div>

    <div class="mgmt-body">
      <LiteratureLibrary v-if="activeKind === 'literature'" embedded :initial-record-id="recordId" />
      <CaseLibrary v-else embedded :initial-record-id="recordId" />
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import LiteratureLibrary from "./LiteratureLibrary.vue";
import CaseLibrary from "./CaseLibrary.vue";
import { LIT_RECORDS, CASE_RECORDS } from "../../data/dorMock";

const route = useRoute();
const router = useRouter();

const TABS = [
  { key: "literature", label: "文献库", count: LIT_RECORDS.length },
  { key: "case", label: "病案库", count: CASE_RECORDS.length },
];

const activeKind = computed(() => (route.query.kind === "case" ? "case" : "literature"));
const recordId = computed(() => String(route.query.record || ""));

function setKind(kind) {
  if (kind === activeKind.value) return;
  router.replace({ query: { kind } });
}
</script>

<style scoped>
.admin-page { width: 100%; height: 100%; padding: 24px 32px; display: flex; flex-direction: column; }

.admin-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.header-text h1 { font-size: 22px; font-weight: 600; color: #1a1a2e; margin: 0 0 4px; }
.header-sub { margin: 0; font-size: 12px; color: #888; }

.mgmt-tabs { flex-shrink: 0; display: flex; align-items: center; gap: 4px; border-bottom: 1px solid #e8e8e8; margin-bottom: 18px; }
.mgmt-tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 16px 11px;
  border: none;
  background: transparent;
  color: #888;
  font-size: 13px;
  cursor: pointer;
  transition: color 0.15s ease;
}
.mgmt-tab:hover { color: #444; }
.mgmt-tab.active { color: #00796b; font-weight: 600; }
.mgmt-tab.active::after {
  content: "";
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: -1px;
  height: 2px;
  border-radius: 2px 2px 0 0;
  background: #00796b;
}
.mgmt-count {
  min-width: 19px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #f1f3f4;
  color: #888;
  font-size: 10px;
  font-weight: 600;
  text-align: center;
}
.mgmt-tab.active .mgmt-count { background: #e0f2f1; color: #00796b; }

.mgmt-body { flex: 1 1 auto; min-height: 0; display: flex; }
</style>
