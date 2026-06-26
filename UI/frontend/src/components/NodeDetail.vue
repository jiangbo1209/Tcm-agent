<template>
  <div class="node-detail">
    <header class="detail-header">
      <h2>{{ title }}</h2>
      <p v-if="meta" class="detail-meta">{{ meta }}</p>
    </header>
    <div v-if="loading" class="detail-loading">
      <div class="loading-bar"><span></span></div>
    </div>
    <div v-else-if="error" class="detail-error">{{ error }}</div>
    <div v-else-if="detail" class="detail-body">
      <template v-if="detail.detail_type === 'paper'">
        <div class="detail-actions">
          <button class="btn-ghost" @click="viewFile" :disabled="!canAccess">查看原文</button>
          <button class="btn-ghost" @click="downloadFile" :disabled="!canAccess">下载</button>
        </div>
        <div class="detail-section">
          <h3>Abstract</h3>
          <p class="detail-text">{{ detail.paper?.abstract || "暂无摘要" }}</p>
        </div>
      </template>
      <template v-else>
        <div class="detail-section">
          <h3>病案核心信息</h3>
          <div class="info-cards">
            <div v-for="field in coreFields" :key="field.label" class="info-card">
              <span class="info-label">{{ field.label }}</span>
              <span class="info-value">{{ field.value || "-" }}</span>
            </div>
          </div>
        </div>
        <div v-if="detail.record_fields?.length" class="detail-section">
          <h3>全部病案信息</h3>
          <div class="fields-list">
            <div v-for="f in detail.record_fields" :key="f.name" class="field-item">
              <div class="field-name">{{ f.name }}</div>
              <div class="field-value">{{ f.value || "-" }}</div>
            </div>
          </div>
        </div>
      </template>
    </div>
    <div v-else class="detail-empty">点击节点查看详情</div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { getNodeDetail, getFileUrl } from "../api/graph";

const props = defineProps({ nodeId: { type: String, default: "" } });

const loading = ref(false);
const error = ref("");
const detail = ref(null);

const title = computed(() => detail.value?.node?.title || "节点详情");
const meta = computed(() => {
  if (!detail.value) return "";
  const n = detail.value.node;
  if (n?.node_type === "paper") return `文献 · 年份：${n.publish_year || "-"}`;
  const d = detail.value.record;
  return d ? `病案 · 诊断：${d.syndrome || d.diagnosis || "-"}` : "";
});
const canAccess = computed(() => detail.value?.paper?.file_name);

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

watch(() => props.nodeId, async (id) => {
  if (!id) { detail.value = null; return; }
  loading.value = true; error.value = ""; detail.value = null;
  try {
    const { data } = await getNodeDetail(id);
    detail.value = data;
  } catch (e) {
    error.value = e.response?.data?.error || "加载失败";
  } finally {
    loading.value = false;
  }
});

async function viewFile() {
  if (!props.nodeId) return;
  try {
    const { data } = await getFileUrl(props.nodeId, "view");
    window.open(data.url, "_blank");
  } catch { error.value = "暂未挂载原始文献文件"; }
}

async function downloadFile() {
  if (!props.nodeId) return;
  try {
    const { data } = await getFileUrl(props.nodeId, "download");
    const a = document.createElement("a"); a.href = data.url; a.download = data.file_name || ""; a.click();
  } catch { error.value = "暂未挂载原始文献文件"; }
}
</script>

<style scoped>
.node-detail { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.detail-header { padding: 14px 16px; border-bottom: 1px solid var(--border); }
.detail-header h2 { margin: 0; font-size: 16px; font-weight: 600; color: #2a3539; }
.detail-meta { margin: 6px 0 0; color: var(--ink-500); font-size: 12px; }
.detail-loading { padding: 40px 16px; display: flex; justify-content: center; }
.loading-bar { width: 200px; height: 6px; border-radius: 999px; background: rgba(0,121,107,0.13); overflow: hidden; }
.loading-bar span { display: block; width: 42%; height: 100%; border-radius: 999px; background: linear-gradient(90deg, rgba(0,121,107,0.2), rgba(0,121,107,0.85), rgba(0,121,107,0.25)); animation: load-progress 1.2s ease-in-out infinite; }
@keyframes load-progress { 0% { transform: translateX(-115%); } 50% { transform: translateX(65%); } 100% { transform: translateX(220%); } }
.detail-error, .detail-empty { padding: 20px 16px; color: var(--ink-500); font-size: 13px; text-align: center; }
.detail-body { padding: 12px 14px; overflow: auto; flex: 1; }
.detail-actions { display: flex; gap: 8px; margin-bottom: 16px; }
.detail-actions .btn-ghost { padding: 6px 12px; font-size: 12px; }
.detail-actions .btn-ghost:disabled { opacity: 0.4; cursor: not-allowed; }
.detail-section { margin-bottom: 18px; }
.detail-section h3 { margin: 0 0 8px; font-size: 13px; color: var(--ink-600); text-transform: uppercase; letter-spacing: 0.6px; }
.detail-text { margin: 0; font-size: 13px; color: var(--ink-900); line-height: 1.65; }
.info-cards { display: grid; gap: 8px; }
.info-card { border: 1px solid rgba(0,121,107,0.18); background: rgba(0,121,107,0.05); border-radius: 10px; padding: 8px 10px; }
.info-label { display: block; font-size: 11px; color: var(--ink-500); }
.info-value { display: block; font-size: 13px; color: var(--ink-900); margin-top: 2px; }
.fields-list { display: grid; gap: 8px; }
.field-item { border: 1px solid rgba(27,42,47,0.08); border-radius: 8px; padding: 8px 10px; background: rgba(255,255,255,0.88); }
.field-name { font-size: 11px; color: var(--ink-500); margin-bottom: 4px; }
.field-value { font-size: 13px; color: var(--ink-900); line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
</style>
