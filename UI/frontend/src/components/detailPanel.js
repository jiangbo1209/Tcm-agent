function asDisplayText(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  const text = String(value).trim();
  return text || "-";
}

function normalizeText(value) {
  return String(value || "").trim();
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function splitTags(value) {
  const raw = normalizeText(value);
  if (!raw || raw === "-") {
    return [];
  }
  return raw
    .split(/[、,，;；\s]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function firstNonEmpty(...values) {
  for (const value of values) {
    const text = normalizeText(value);
    if (text && text !== "-") {
      return text;
    }
  }
  return "-";
}

function pickField(recordMap, keys) {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(recordMap, key)) {
      const value = normalizeText(recordMap[key]);
      if (value) {
        return value;
      }
    }
  }
  return "-";
}

function buildRefLink(refValue) {
  const raw = normalizeText(refValue);
  if (!raw || raw === "-") {
    return null;
  }
  if (/^https?:\/\//i.test(raw)) {
    return raw;
  }
  if (/^10\.\d{4,9}\//.test(raw)) {
    return `https://doi.org/${raw}`;
  }
  return null;
}

function renderDownloadIcon() {
  return `
    <svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 4v10m0 0 4-4m-4 4-4-4M5 19h14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  `;
}

function renderViewIcon() {
  return `
    <svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11z" fill="none" stroke="currentColor" stroke-width="1.8"/>
      <path d="M8 8.5h8M8 12h8M8 15.5h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
    </svg>
  `;
}

function renderActions({ nodeId, nodeType, canAccessFile }) {
  const disabledAttr = canAccessFile ? "" : "disabled aria-disabled=\"true\"";
  const disabledClass = canAccessFile ? "" : " is-disabled";

  return `
    <div class="detail-actions">
      <button
        class="detail-btn detail-action-btn${disabledClass}"
        type="button"
        data-action="download"
        data-node-id="${escapeHtml(nodeId)}"
        data-node-type="${escapeHtml(nodeType)}"
        ${disabledAttr}
      >
        ${renderDownloadIcon()}
        <span class="btn-text">下载</span>
      </button>
      <button
        class="detail-btn detail-action-btn${disabledClass}"
        type="button"
        data-action="view"
        data-node-id="${escapeHtml(nodeId)}"
        data-node-type="${escapeHtml(nodeType)}"
        ${disabledAttr}
      >
        ${renderViewIcon()}
        <span class="btn-text">查看原文</span>
      </button>
    </div>
  `;
}

function renderRef(refValue) {
  const text = escapeHtml(asDisplayText(refValue));
  const link = buildRefLink(refValue);
  const icon = `
    <svg class="link-icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M10.5 2.5h3v3h-1.5V4.56L8.3 8.26 7.24 7.2l3.7-3.7H10.5V2.5ZM3.5 4.5h4v1.5h-4v6h6v-4H11.5v4.5a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1Z" fill="currentColor"/>
    </svg>
  `;

  if (link) {
    return `
      <div class="detail-ref">
        <span class="ref-label">DOI/编号</span>
        <a class="ref-link" href="${escapeHtml(link)}" target="_blank" rel="noopener">${text}${icon}</a>
      </div>
    `;
  }

  return `
    <div class="detail-ref">
      <span class="ref-label">DOI/编号</span>
      <span class="ref-value">${text}${icon}</span>
    </div>
  `;
}

export function createDetailPanel({ detailTitle, detailMeta, detailBody }) {
  let currentNodeId = "";

  function applyContent(html) {
    detailBody.innerHTML = `<div class="detail-content detail-content-enter">${html}</div>`;
    const content = detailBody.querySelector(".detail-content");
    if (!content) {
      return;
    }
    window.requestAnimationFrame(() => {
      content.classList.add("is-visible");
    });
  }

  function clear() {
    currentNodeId = "";
    detailTitle.textContent = "节点详情";
    detailMeta.textContent = "";
    detailBody.innerHTML = "";
  }

  function setLoading(nodeModel) {
    const fallbackTitle = normalizeText(nodeModel?.title) || normalizeText(nodeModel?.id) || "节点详情";

    detailTitle.textContent = fallbackTitle;
    detailMeta.textContent = "";
    detailBody.innerHTML = `
      <div class="detail-loading-wrap" role="status" aria-live="polite">
        <div class="detail-loading-bar"><span></span></div>
      </div>
    `;
  }

  function renderError(message) {
    detailMeta.textContent = "详情加载失败";
    detailBody.innerHTML = `<div class="detail-empty">${escapeHtml(asDisplayText(message || "请稍后重试"))}</div>`;
  }

  function renderPaper(node, paper) {
    const title = node.title || node.id;
    const authors = paper?.authors || "-";
    const year = paper?.pub_year || node.publish_year || "-";
    const refValue = paper?.file_name || node.id;
    currentNodeId = String(node.id || "");
    const hasFileKey = normalizeText(paper?.file_key) !== "";

    detailTitle.textContent = title;
    detailMeta.textContent = `作者：${asDisplayText(authors)} · 年份：${asDisplayText(year)}`;

    if (!paper) {
      detailBody.innerHTML = '<div class="detail-empty">未查询到文献明细</div>';
      return;
    }

    const abstract = paper.abstract || paper.keywords || "暂无摘要";

    applyContent(`
      <div class="detail-top">
        ${renderActions({
          nodeId: String(node.id || ""),
          nodeType: "paper",
          canAccessFile: hasFileKey
        })}
        ${renderRef(refValue)}
      </div>
      <div class="detail-section">
        <h3>Abstract</h3>
        <p class="detail-text">${escapeHtml(asDisplayText(abstract))}</p>
      </div>
    `);
  }

  function renderRecord(node, fields) {
    const title = firstNonEmpty(node.title, node.id);
    currentNodeId = String(node.id || "");
    detailTitle.textContent = title;

    if (!Array.isArray(fields) || fields.length === 0) {
      detailBody.innerHTML = '<div class="detail-empty">未查询到病案明细</div>';
      return;
    }

    const recordMap = {};
    fields.forEach((item) => {
      recordMap[item.name] = item.value;
    });

    const caseTitle = pickField(recordMap, ["论文名称", "病案标题", "标题", "病例标题"]);
    const patientAge = firstNonEmpty(
      pickField(recordMap, ["年龄", "患者年龄", "就诊年龄"]),
      node.age,
      node.metric_value
    );
    const menstrual = pickField(recordMap, ["月经情况", "月经史", "月经", "经期情况", "经量"]);
    const tcmDiag = pickField(recordMap, ["中医证候诊断", "中医诊断", "辨证"]);
    const westernDiag = pickField(recordMap, ["西医病名诊断", "西医诊断", "西医病名"]);
    const therapy = pickField(recordMap, ["治法", "治疗原则", "治则"]);
    const formulaName = pickField(recordMap, ["方剂名称", "方剂", "方名"]);
    const formulaComposition = pickField(recordMap, ["详细组成", "方剂详细组成", "方剂组成", "组成"]);
    const notes = pickField(recordMap, ["按语/评价说明", "刻下症", "病案摘要", "主诉"]);
    const refValue = node.id;

    detailMeta.textContent = `病案 · 年龄：${asDisplayText(patientAge)} · 诊断：${asDisplayText(tcmDiag !== "-" ? tcmDiag : westernDiag)}`;

    const herbTags = splitTags(formulaComposition === "-" ? formulaName : formulaComposition)
      .map((item) => `<span class="herb-tag">${escapeHtml(item)}</span>`)
      .join("");

    const allFieldsHtml = fields
      .map((item) => {
        const name = escapeHtml(asDisplayText(item?.name));
        const value = escapeHtml(asDisplayText(item?.value));
        return `
          <div class="record-field-row">
            <div class="record-field-name">${name}</div>
            <div class="record-field-value">${value}</div>
          </div>
        `;
      })
      .join("");

    applyContent(`
      <div class="detail-top">
        ${renderActions({
          nodeId: String(node.id || ""),
          nodeType: "record",
          canAccessFile: false
        })}
        ${renderRef(refValue)}
      </div>

      <div class="detail-section">
        <h3>病案核心信息</h3>
        <div class="info-cards">
          <div class="info-card">
            <span class="info-label">病案标题</span>
            <span class="info-value">${escapeHtml(asDisplayText(caseTitle === "-" ? title : caseTitle))}</span>
          </div>
          <div class="info-card">
            <span class="info-label">患者年龄</span>
            <span class="info-value">${escapeHtml(asDisplayText(patientAge))}</span>
          </div>
          <div class="info-card">
            <span class="info-label">月经情况</span>
            <span class="info-value">${escapeHtml(asDisplayText(menstrual))}</span>
          </div>
          <div class="info-card">
            <span class="info-label">中医诊断</span>
            <span class="info-value">${escapeHtml(asDisplayText(tcmDiag))}</span>
          </div>
          <div class="info-card">
            <span class="info-label">西医诊断</span>
            <span class="info-value">${escapeHtml(asDisplayText(westernDiag))}</span>
          </div>
          <div class="info-card">
            <span class="info-label">治法</span>
            <span class="info-value">${escapeHtml(asDisplayText(therapy))}</span>
          </div>
        </div>
      </div>

      <div class="detail-section">
        <h3>方剂信息</h3>
        <div class="info-cards">
          <div class="info-card">
            <span class="info-label">方剂名称</span>
            <span class="info-value">${escapeHtml(asDisplayText(formulaName))}</span>
          </div>
          <div class="info-card">
            <span class="info-label">详细组成</span>
            <span class="info-value">${escapeHtml(asDisplayText(formulaComposition))}</span>
          </div>
        </div>
        <div class="formula-block">
          <span class="info-label">组成标签</span>
          <div class="herb-tags">${herbTags || "<span class=\"empty-tag\">暂无组成标签</span>"}</div>
        </div>
      </div>

      <div class="detail-section">
        <h3>病案摘要</h3>
        <p class="detail-text">${escapeHtml(asDisplayText(notes))}</p>
      </div>

      <div class="detail-section">
        <details class="record-all-fields" open>
          <summary>
            <span>全部病案信息</span>
            <span class="record-fields-count">${fields.length} 项</span>
          </summary>
          <div class="record-fields-list">
            ${allFieldsHtml}
          </div>
        </details>
      </div>
    `);
  }

  function render(payload) {
    if (!payload || !payload.node) {
      clear();
      return;
    }

    const nodeType = normalizeText(payload.node.node_type);
    const detailType = normalizeText(payload.detail_type);
    const effectiveType = nodeType || detailType;

    if (effectiveType === "paper") {
      renderPaper(payload.node, payload.paper);
      return;
    }

    renderRecord(payload.node, payload.record_fields || []);
  }

  return { clear, setLoading, render, renderError };
}
