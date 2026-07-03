<template>
  <div class="detail-page">
    <div v-if="loading" class="detail-state">加载中...</div>
    <div v-else-if="error" class="detail-state error">{{ error }}</div>

    <div v-else-if="detail" class="detail-content">
      <header class="detail-header">
        <span class="result-type-badge" :class="detail.detail_type">
          {{ detail.detail_type === "record" ? "病案" : "文献" }}
        </span>
        <h1>{{ detail.node?.title || "未命名" }}</h1>
        <p v-if="metaText" class="detail-meta">{{ metaText }}</p>
      </header>

      <template v-if="detail.detail_type === 'paper' && detail.paper">
        <section class="detail-section">
          <h2>文献信息</h2>
          <dl class="detail-grid">
            <template v-for="row in paperRows" :key="row.label">
              <dt>{{ row.label }}</dt>
              <dd>{{ row.value }}</dd>
            </template>
          </dl>
        </section>
        <section v-if="detail.paper.abstract" class="detail-section">
          <h2>摘要</h2>
          <p class="detail-abstract">{{ detail.paper.abstract }}</p>
        </section>
        <div class="detail-actions">
          <button class="btn-ghost" @click="viewFile" :disabled="!canAccessFile">查看原文</button>
          <button class="btn-ghost" @click="downloadFile" :disabled="!canAccessFile">下载</button>
        </div>
        <div v-if="fileError" class="detail-state error file-error">{{ fileError }}</div>
      </template>

      <template v-else-if="detail.detail_type === 'record'">
        <section class="detail-section">
          <h2>病案核心信息</h2>
          <div class="info-cards">
            <div v-for="field in coreFields" :key="field.label" class="info-card">
              <span class="info-label">{{ field.label }}</span>
              <span class="info-value">{{ field.value || "-" }}</span>
            </div>
          </div>
        </section>
        <section v-if="recordRows.length" class="detail-section">
          <h2>全部病案信息</h2>
          <div class="fields-list">
            <div v-for="f in recordRows" :key="f.name" class="field-item">
              <div class="field-name">{{ f.name }}</div>
              <div class="field-value">{{ f.value || "-" }}</div>
            </div>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import { getNodeDetail, getDetailByFile, getFileUrl, getFileUrlByUuid } from "../api/graph";

const route = useRoute();

const loading = ref(false);
const error = ref("");
const fileError = ref("");
const detail = ref(null);

const nodeId = computed(() => route.params.nodeId);
const fileUuid = computed(() => route.params.fileUuid);
const sourceType = computed(() => route.query.source_type);
const hasFileUuid = computed(() => !!fileUuid.value && !!sourceType.value);

const metaText = computed(() => {
  if (!detail.value) return "";
  const n = detail.value.node;
  if (n?.node_type === "paper") {
    const p = detail.value.paper;
    return `作者：${p?.authors || "-"} · 年份：${p?.pub_year || n.publish_year || "-"}`;
  }
  const r = detail.value.record;
  return r ? `病案 · 诊断：${r.syndrome || r.diagnosis || "-"}` : "";
});

const canAccessFile = computed(() => !!detail.value?.paper?.file_name);

const paperRows = computed(() => {
  const p = detail.value?.paper || {};
  return [
    ["作者", p.authors],
    ["期刊", p.journal],
    ["年份", p.pub_year],
    ["关键词", p.keywords],
    ["文件", p.file_name],
  ]
    .filter(([, v]) => v != null && String(v).trim() !== "")
    .map(([label, value]) => ({ label, value }));
});

const coreFields = computed(() => {
  const r = detail.value?.record;
  if (!r) return [];
  return [
    { label: "诊断", value: r.diagnosis },
    { label: "证型", value: r.syndrome },
    { label: "治法", value: r.treatment_principle },
    { label: "处方", value: r.prescription },
  ].filter(f => f.value);
});

const recordRows = computed(() =>
  (detail.value?.record_fields || [])
    .filter(f => f.value != null && String(f.value).trim() !== "")
);

async function loadDetail(id, fid, stype) {
  if (!id && !(fid && stype)) return;
  loading.value = true;
  error.value = "";
  fileError.value = "";
  detail.value = null;
  try {
    let resp;
    if (fid && stype) {
      resp = await getDetailByFile(fid, stype);
    } else {
      resp = await getNodeDetail(id);
    }
    detail.value = resp.data;
  } catch (e) {
    error.value = e.response?.data?.error || e.response?.data?.detail || "详情加载失败";
  } finally {
    loading.value = false;
  }
}

async function viewFile() {
  fileError.value = "";
  try {
    let resp;
    if (hasFileUuid.value) {
      resp = await getFileUrlByUuid(fileUuid.value, sourceType.value, "view");
    } else {
      resp = await getFileUrl(nodeId.value, "view");
    }
    window.open(resp.data.url, "_blank");
  } catch {
    fileError.value = "暂未挂载原始文献文件";
  }
}

async function downloadFile() {
  fileError.value = "";
  try {
    let resp;
    if (hasFileUuid.value) {
      resp = await getFileUrlByUuid(fileUuid.value, sourceType.value, "download");
    } else {
      resp = await getFileUrl(nodeId.value, "download");
    }
    const a = document.createElement("a");
    a.href = resp.data.url;
    a.download = resp.data.file_name || "";
    a.click();
  } catch {
    fileError.value = "暂未挂载原始文献文件";
  }
}

onMounted(() => loadDetail(nodeId.value, fileUuid.value, sourceType.value));
watch(() => [route.params.nodeId, route.params.fileUuid, route.query.source_type], ([nid, fid, stype]) => {
  loadDetail(nid, fid, stype);
});
</script>

<style scoped>
.detail-page { min-height: 100vh; overflow-y: auto; padding: 32px 24px; max-width: 860px; margin: 0 auto; width: 100%; background: var(--bg); }
.detail-state { text-align: center; padding: 60px 20px; color: var(--ink-500); font-size: 15px; }
.detail-state.error { color: var(--danger); }
.file-error { padding: 8px 0 0; font-size: 13px; text-align: left; }
.detail-header { margin-bottom: 28px; }
.detail-header h1 { margin: 10px 0 8px; font-size: 24px; font-weight: 600; color: var(--ink-900); line-height: 1.4; }
.detail-meta { font-size: 14px; color: var(--ink-500); }
.result-type-badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.result-type-badge.paper { background: rgba(0,121,107,0.1); color: var(--teal); }
.result-type-badge.record { background: rgba(199,124,2,0.15); color: #b06a00; }
.detail-section { margin-bottom: 28px; }
.detail-section h2 { margin: 0 0 14px; font-size: 16px; font-weight: 600; color: var(--ink-700); border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.detail-grid { display: grid; grid-template-columns: 100px 1fr; gap: 12px 16px; }
.detail-grid dt { color: var(--ink-500); font-size: 13px; font-weight: 500; }
.detail-grid dd { margin: 0; color: var(--ink-900); font-size: 14px; line-height: 1.65; overflow-wrap: anywhere; }
.detail-abstract { font-size: 14px; color: var(--ink-600); line-height: 1.8; }
.detail-actions { display: flex; gap: 10px; margin-top: 20px; }
.info-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.info-card { border: 1px solid rgba(0,121,107,0.18); background: rgba(0,121,107,0.04); border-radius: 12px; padding: 14px 16px; }
.info-label { display: block; font-size: 12px; color: var(--ink-500); margin-bottom: 4px; }
.info-value { display: block; font-size: 14px; color: var(--ink-900); line-height: 1.6; }
.fields-list { display: grid; gap: 10px; }
.field-item { border: 1px solid rgba(27,42,47,0.08); border-radius: 10px; padding: 12px 14px; background: var(--panel); }
.field-name { font-size: 12px; color: var(--ink-500); margin-bottom: 4px; }
.field-value { font-size: 14px; color: var(--ink-900); line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
</style>
