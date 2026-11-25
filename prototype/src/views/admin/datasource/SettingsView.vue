<template>
  <div class="settings-page">
    <section class="settings-head">
      <button class="btn-primary" @click="saveAll">保存配置</button>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>Prompt 模板</h3>
      </div>
      <table class="pool-table">
        <thead><tr><th>研究类型</th><th>模板版本</th><th>更新时间</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="p in prompts" :key="p.type">
            <td>{{ p.type }}</td>
            <td class="mono">v{{ p.version }}</td>
            <td class="muted">{{ p.updatedAt }}</td>
            <td><span class="badge" :class="p.active ? 'badge-ok' : 'badge-muted'">{{ p.active ? "启用" : "停用" }}</span></td>
            <td><button class="btn-sm" @click="editPrompt(p)">编辑</button></td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>枚举词典</h3>
      </div>
      <div class="dict-grid">
        <div v-for="d in dictionaries" :key="d.name" class="dict-card">
          <div class="dict-head"><strong>{{ d.name }}</strong><span>{{ d.items.length }} 项</span></div>
          <div class="chips">
            <span v-for="(item, i) in d.items" :key="item + i" class="chip">
              {{ item }}
              <button class="chip-x" @click="removeDictItem(d, i)">×</button>
            </span>
          </div>
          <div class="dict-add">
            <input v-model="d.newItem" class="filter-input" :placeholder="`新增${d.name}`" @keyup.enter="addDictItem(d)" />
            <button class="btn-sm" @click="addDictItem(d)">添加</button>
          </div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>校验阈值</h3>
      </div>
      <div class="form-grid">
        <label class="form-item">
          <span>最低置信度</span>
          <input v-model.number="thresholds.minConfidence" type="number" step="0.05" min="0" max="1" class="filter-input" />
          <small>低于该值的字段标记为低置信</small>
        </label>
        <label class="form-item">
          <span>必填策略</span>
          <select v-model="thresholds.requiredPolicy" class="filter-select">
            <option value="block">必填缺失则阻断通过</option>
            <option value="warn">仅提示，允许人工通过</option>
          </select>
          <small>控制校验通过条件</small>
        </label>
        <label class="form-item">
          <span>单位识别失败处理</span>
          <select v-model="thresholds.unitPolicy" class="filter-select">
            <option value="warn">标记问题继续</option>
            <option value="block">阻断通过</option>
          </select>
          <small>AMH/FSH/AFC 等单位</small>
        </label>
        <label class="form-item">
          <span>最大并发任务</span>
          <input v-model.number="thresholds.concurrency" type="number" min="1" max="16" class="filter-input" />
          <small>同时执行的抽取任务数</small>
        </label>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><h3>模型参数</h3></div>
      <div class="form-grid">
        <label class="form-item">
          <span>模型</span>
          <input v-model="model.name" class="filter-input" />
        </label>
        <label class="form-item">
          <span>温度</span>
          <input v-model.number="model.temperature" type="number" step="0.1" min="0" max="2" class="filter-input" />
        </label>
        <label class="form-item">
          <span>单篇最大 token</span>
          <input v-model.number="model.maxTokens" type="number" class="filter-input" />
        </label>
        <label class="form-item">
          <span>超时（秒）</span>
          <input v-model.number="model.timeout" type="number" class="filter-input" />
        </label>
      </div>
    </section>

    <transition name="toast"><div v-if="toastVisible" class="toast">配置已保存（原型）</div></transition>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";

const prompts = reactive([
  { type: "META分析/系统评价", version: "2.1", updatedAt: "2025-03-10 14:20", active: true },
  { type: "随机对照试验(RCT)", version: "1.8", updatedAt: "2025-03-08 09:10", active: true },
  { type: "队列研究", version: "1.5", updatedAt: "2025-03-05 16:40", active: true },
  { type: "病例对照研究", version: "1.3", updatedAt: "2025-02-28 11:05", active: true },
  { type: "横断面研究", version: "1.2", updatedAt: "2025-02-20 10:30", active: true },
  { type: "个案报道/病例系列", version: "1.1", updatedAt: "2025-02-15 15:00", active: true },
  { type: "准实验/前后对照", version: "1.0", updatedAt: "2025-02-10 09:45", active: false },
  { type: "综述", version: "1.0", updatedAt: "2025-02-01 13:20", active: false },
  { type: "其他", version: "1.0", updatedAt: "2025-01-25 17:10", active: false },
]);

const dictionaries = reactive([
  { name: "证型", items: ["肾虚证", "肝肾阴虚证", "脾肾阳虚证", "肝郁气滞证", "血瘀证", "气血两虚证", "痰湿证", "肾虚肝郁证", "肾虚血瘀证", "复合证型", "其他"], newItem: "" },
  { name: "干预类型", items: ["中药内服", "针灸", "电针", "艾灸", "埋线", "穴位贴敷", "耳穴压豆", "中药+针灸", "中西医结合", "推拿", "其他"], newItem: "" },
  { name: "促排方案", items: ["微刺激", "拮抗剂方案", "短方案", "长方案", "黄体期促排", "自然周期", "双刺激", "非降调节方案", "其他"], newItem: "" },
  { name: "治疗时机", items: ["孕前调理", "周期调理", "促排前", "促排期", "移植前后", "黄体支持期", "全程"], newItem: "" },
]);

const thresholds = reactive({ minConfidence: 0.6, requiredPolicy: "block", unitPolicy: "warn", concurrency: 4 });
const model = reactive({ name: "qwen2.5-72b-instruct", temperature: 0.1, maxTokens: 8192, timeout: 120 });

const toastVisible = ref(false);
let timer = null;
function saveAll() {
  toastVisible.value = true;
  clearTimeout(timer);
  timer = setTimeout(() => (toastVisible.value = false), 2200);
}
function editPrompt(p) {
  p.version = (Number(p.version) + 0.1).toFixed(1);
  p.updatedAt = new Date().toISOString().slice(0, 16).replace("T", " ");
}
function addDictItem(d) {
  const v = d.newItem.trim();
  if (!v) return;
  if (!d.items.includes(v)) d.items.push(v);
  d.newItem = "";
}
function removeDictItem(d, i) {
  d.items.splice(i, 1);
}
</script>

<style scoped>
.settings-head { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-bottom: 14px; }
.settings-head h2 { margin: 0 0 4px; font-size: 16px; }
.desc { margin: 0; font-size: 12px; color: var(--ink-400); }
.panel { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; margin-bottom: 14px; }
.panel-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 12px; }
.panel-head h3 { margin: 0; font-size: 14px; }
.hint { font-size: 11px; color: var(--ink-400); }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
.muted { color: var(--ink-400); font-size: 12px; }

.dict-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.dict-card { border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
.dict-head { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 12px; }
.dict-head span { color: var(--ink-400); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: 999px; background: var(--teal-soft); color: var(--teal-dark); font-size: 11px; }
.chip-x { border: none; background: transparent; color: var(--teal-dark); cursor: pointer; font-size: 12px; line-height: 1; }
.dict-add { display: flex; gap: 6px; }
.dict-add .filter-input { flex: 1; padding: 5px 8px; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 18px; }
.form-item { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--ink-700); }
.form-item small { font-size: 10px; color: var(--ink-400); }

.toast { position: fixed; top: 24px; right: 24px; background: var(--teal); color: #fff; padding: 10px 16px; border-radius: 8px; font-size: 13px; }
.toast-enter-active, .toast-leave-active { transition: opacity .2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; }
</style>
