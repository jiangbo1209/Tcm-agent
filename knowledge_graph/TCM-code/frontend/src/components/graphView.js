const YEAR_DOMAIN = [1963, 2024];
const AGE_DOMAIN = [18, 75];
const SIZE_DOMAIN = [0.8, 3.0];
const DISTANCE_RANGE = [90, 320];
const DEFAULT_NODE_STROKE = "#aeb7c2";
const SEED_NODE_STROKE = "#7e3af2";
const HOVER_NODE_STROKE = "#4f46e5";
const EDGE_BASE_COLOR = "#aeb7c2";
const LABEL_MAX_CHARS = 16;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalize(value, domain) {
  const safeValue = Number.isFinite(value) ? value : domain[0];
  const clamped = clamp(safeValue, domain[0], domain[1]);
  if (domain[0] === domain[1]) {
    return 0.5;
  }
  return (clamped - domain[0]) / (domain[1] - domain[0]);
}

function mapNodeSize(topK) {
  const t = normalize(topK, SIZE_DOMAIN);
  return Math.round(20 + t * (72 - 20));
}

function truncateLabel(text, maxChars) {
  const raw = String(text || "").trim();
  if (raw.length <= maxChars) {
    return raw;
  }
  return `${raw.slice(0, Math.max(1, maxChars - 1))}…`;
}

function hexToRgb(hex) {
  let normalized = String(hex || "").replace("#", "").trim();
  if (normalized.length === 3) {
    normalized = normalized
      .split("")
      .map((ch) => ch + ch)
      .join("");
  }

  if (!/^[0-9a-fA-F]{6}$/.test(normalized)) {
    return { r: 0, g: 0, b: 0 };
  }

  return {
    r: parseInt(normalized.slice(0, 2), 16),
    g: parseInt(normalized.slice(2, 4), 16),
    b: parseInt(normalized.slice(4, 6), 16)
  };
}

function mixHexColor(startHex, endHex, t) {
  const from = hexToRgb(startHex);
  const to = hexToRgb(endHex);
  const p = clamp(Number.isFinite(t) ? t : 0, 0, 1);

  const r = Math.round(from.r + (to.r - from.r) * p);
  const g = Math.round(from.g + (to.g - from.g) * p);
  const b = Math.round(from.b + (to.b - from.b) * p);

  return `rgb(${r}, ${g}, ${b})`;
}

function mapNodeColor(nodeType, publishYear, age) {
  if (nodeType === "paper") {
    const yearT = normalize(publishYear, YEAR_DOMAIN);
    return mixHexColor("#c9f4ee", "#00796b", yearT);
  }

  const ageT = normalize(age, AGE_DOMAIN);
  return mixHexColor("#fff2b3", "#b86a00", ageT);
}

function mapDistance(similarityScore) {
  const score = clamp(Number(similarityScore) || 0, 0, 1);
  return Math.round(DISTANCE_RANGE[1] - score * (DISTANCE_RANGE[1] - DISTANCE_RANGE[0]));
}

function mapEdgeOpacity(similarityScore) {
  const score = clamp(Number(similarityScore) || 0, 0, 1);
  return Number((0.25 + score * 0.65).toFixed(3));
}

function mapNode(rawNode) {
  const nodeType = rawNode.node_type === "paper" ? "paper" : "record";
  const topKValue = Number(rawNode.top_k_value);
  const publishYear = Number(rawNode.publish_year ?? rawNode.metric_value);
  const age = Number(rawNode.age ?? rawNode.metric_value);
  const size = mapNodeSize(topKValue);
  const fullLabel = rawNode.title || String(rawNode.id);
  const shortLabel = truncateLabel(fullLabel, LABEL_MAX_CHARS);

  return {
    id: String(rawNode.id),
    node_type: nodeType,
    title: rawNode.title || String(rawNode.id),
    label: shortLabel,
    full_label: fullLabel,
    short_label: shortLabel,
    metric_value: Number(rawNode.metric_value),
    publish_year: Number.isFinite(publishYear) ? publishYear : null,
    age: Number.isFinite(age) ? age : null,
    top_k_value: Number.isFinite(topKValue) ? topKValue : null,
    type: nodeType === "paper" ? "circle" : "rect",
    size: nodeType === "paper" ? size : [size, size],
    style: {
      fill: mapNodeColor(nodeType, publishYear, age),
      stroke: DEFAULT_NODE_STROKE,
      lineWidth: 1,
      cursor: "pointer"
    },
    labelCfg: {
      style: {
        fill: "#153a47",
        fontSize: 11,
        fontWeight: 400,
        background: {
          fill: "rgba(255,255,255,0.52)",
          radius: 4,
          padding: [1, 2]
        }
      },
      position: "bottom",
      offset: 7
    }
  };
}

function mapEdge(rawEdge) {
  const edgeTypeRaw = String(rawEdge.edge_type || "paper-paper");
  const edgeType = edgeTypeRaw === "record-paper" ? "paper-record" : edgeTypeRaw;
  const score = clamp(Number(rawEdge.similarity_score) || 0, 0, 1);
  const baseOpacity = mapEdgeOpacity(score);

  let style;
  if (edgeType === "paper-record") {
    style = {
      stroke: EDGE_BASE_COLOR,
      lineWidth: 3.4 + score * 1.4,
      lineDash: null,
      opacity: baseOpacity,
      endArrow: false
    };
  } else if (edgeType === "record-record") {
    style = {
      stroke: EDGE_BASE_COLOR,
      lineWidth: 1.5 + score * 0.7,
      lineDash: [7, 5],
      opacity: baseOpacity,
      endArrow: false
    };
  } else {
    style = {
      stroke: EDGE_BASE_COLOR,
      lineWidth: 1 + score * 0.6,
      lineDash: null,
      opacity: baseOpacity,
      endArrow: false
    };
  }

  return {
    id: String(rawEdge.id || `${rawEdge.source}->${rawEdge.target}|${edgeType}`),
    source: String(rawEdge.source),
    target: String(rawEdge.target),
    edge_type: edgeType,
    similarity_score: score,
    base_opacity: baseOpacity,
    type: "line",
    style
  };
}

export function createGraphView(
  container,
  {
    store,
    onNodeHover,
    onNodeDetail,
    fetchExpandData,
    onExpandStart,
    onExpandError,
    onExpandSuccess
  }
) {
  const graph = new G6.Graph({
    container,
    width: container.clientWidth,
    height: container.clientHeight,
    modes: {
      default: ["drag-canvas", "zoom-canvas", "drag-node"]
    },
    defaultNode: {
      type: "circle",
      size: 26,
      style: {
        lineWidth: 1,
        stroke: DEFAULT_NODE_STROKE,
        fill: "#e6edf5"
      }
    },
    defaultEdge: {
      style: {
        stroke: EDGE_BASE_COLOR,
        opacity: 0.5
      }
    },
    layout: {
      type: "gForce",
      preventOverlap: true,
      minMovement: 0.2,
      damping: 0.92,
      maxSpeed: 220,
      center: [container.clientWidth / 2, container.clientHeight / 2],
      linkDistance: (edge) => mapDistance(edge.similarity_score)
    }
  });
  graph.data({ nodes: [], edges: [] });
  graph.render();

  let activeSeedNodeId = null;

  function ensureOverlay() {
    const parent = container.parentElement;
    if (!parent) {
      return;
    }
    if (parent.querySelector(".graph-overlay")) {
      return;
    }

    const overlay = document.createElement("div");
    overlay.className = "graph-overlay";
    overlay.innerHTML = `
      <div class="zoom-controls">
        <button type="button" class="icon-btn" data-action="zoom-in" aria-label="放大" title="放大">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
        <button type="button" class="icon-btn" data-action="zoom-out" aria-label="缩小" title="缩小">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M5 12h14" />
          </svg>
        </button>
        <button type="button" class="icon-btn" data-action="fit" aria-label="适配视图" title="适配视图">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M8 4H4v4M16 4h4v4M20 16v4h-4M8 20H4v-4" />
            <path d="M9 9h6v6H9z" />
          </svg>
        </button>
      </div>
      <div class="year-legend">
        <div class="year-legend-labels">
          <span>1963</span>
          <span>2024</span>
        </div>
        <div class="year-bar"></div>
      </div>
    `;

    overlay.addEventListener("click", (event) => {
      const target = event.target.closest("button");
      if (!target) {
        return;
      }
      const action = target.dataset.action;
      if (action === "zoom-in") {
        graph.zoom(1.12);
      } else if (action === "zoom-out") {
        graph.zoom(0.9);
      } else if (action === "fit") {
        graph.fitView(20);
      }
    });

    parent.appendChild(overlay);
  }

  function isSeedNodeId(nodeId) {
    return !!activeSeedNodeId && activeSeedNodeId === nodeId;
  }

  function applyNodeBaseStyle(nodeItem) {
    const nodeId = nodeItem.getModel().id;
    const model = nodeItem.getModel();
    const label = model.short_label || model.label;
    if (isSeedNodeId(nodeId)) {
      graph.updateItem(nodeItem, {
        style: {
          stroke: SEED_NODE_STROKE,
          lineWidth: 4,
          opacity: 1
        },
        label: model.full_label || model.label,
        labelCfg: {
          style: {
            opacity: 1
          }
        }
      });
      return;
    }

    graph.updateItem(nodeItem, {
      style: {
        stroke: DEFAULT_NODE_STROKE,
        lineWidth: 1,
        opacity: 1
      },
      label,
      labelCfg: {
        style: {
          opacity: 0.9
        }
      }
    });
  }

  function applyEdgeBaseStyle(edgeItem) {
    const model = edgeItem.getModel();
    const baseOpacity = Number.isFinite(model.base_opacity)
      ? model.base_opacity
      : Number(model.style?.opacity) || 0.5;
    graph.updateItem(edgeItem, {
      style: {
        stroke: EDGE_BASE_COLOR,
        opacity: baseOpacity
      }
    });
  }

  function resetHoverEffect() {
    const nodes = graph.getNodes();
    const edges = graph.getEdges();

    for (const node of nodes) {
      applyNodeBaseStyle(node);
    }
    for (const edge of edges) {
      applyEdgeBaseStyle(edge);
    }
  }

  function applyHoverEffect(focusItem) {
    if (!focusItem) {
      resetHoverEffect();
      return;
    }

    const focusId = focusItem.getModel().id;
    const relatedNodeIds = new Set([focusId]);
    const relatedEdgeIds = new Set();

    const connectedEdges = focusItem.getEdges ? focusItem.getEdges() : [];
    for (const edge of connectedEdges) {
      const edgeModel = edge.getModel();
      if (edgeModel?.id) {
        relatedEdgeIds.add(edgeModel.id);
      }

      const source = edge.getSource?.();
      const target = edge.getTarget?.();
      if (source?.getModel()?.id) {
        relatedNodeIds.add(source.getModel().id);
      }
      if (target?.getModel()?.id) {
        relatedNodeIds.add(target.getModel().id);
      }
    }

    for (const node of graph.getNodes()) {
      const nodeId = node.getModel().id;
      const isFocus = nodeId === focusId;
      const isNeighbor = !isFocus && relatedNodeIds.has(nodeId);
      const isRelated = isFocus || isNeighbor;

      if (!isRelated) {
        graph.updateItem(node, {
          style: {
            opacity: 0.1
          },
          label: node.getModel().short_label || node.getModel().label,
          labelCfg: {
            style: {
              opacity: 0.1
            }
          }
        });
        continue;
      }

      if (isSeedNodeId(nodeId)) {
        graph.updateItem(node, {
          style: {
            stroke: SEED_NODE_STROKE,
            lineWidth: 4,
            opacity: 1
          },
          label: node.getModel().full_label || node.getModel().label,
          labelCfg: {
            style: {
              opacity: 1
            }
          }
        });
        continue;
      }

      graph.updateItem(node, {
        style: {
          stroke: HOVER_NODE_STROKE,
          lineWidth: isFocus ? 3 : 2,
          opacity: 1
        },
        label: node.getModel().full_label || node.getModel().label,
        labelCfg: {
          style: {
            opacity: 1
          }
        }
      });
    }

    for (const edge of graph.getEdges()) {
      const model = edge.getModel();
      const edgeId = model.id;
      const isRelatedEdge = relatedEdgeIds.has(edgeId);
      const baseOpacity = Number.isFinite(model.base_opacity)
        ? model.base_opacity
        : Number(model.style?.opacity) || 0.5;
      const focusOpacity = Math.min(1, baseOpacity + 0.18);
      const fadeOpacity = Math.max(0.04, baseOpacity * 0.2);

      graph.updateItem(edge, {
        style: {
          stroke: EDGE_BASE_COLOR,
          opacity: isRelatedEdge ? focusOpacity : fadeOpacity
        }
      });
    }
  }

  function markSeedNode(nodeId) {
    if (activeSeedNodeId && activeSeedNodeId !== nodeId) {
      const previous = graph.findById(activeSeedNodeId);
      if (previous) {
        applyNodeBaseStyle(previous);
      }
    }

    activeSeedNodeId = nodeId;
    const current = graph.findById(nodeId);
    if (current) {
      applyNodeBaseStyle(current);
    }
  }

  function mergeGraphIncremental(payload) {
    const incomingNodes = Array.isArray(payload.nodes) ? payload.nodes.map(mapNode) : [];
    const incomingEdges = Array.isArray(payload.edges) ? payload.edges.map(mapEdge) : [];

    const newNodes = incomingNodes.filter((node) => !store.nodeMap.has(node.id));
    const newEdges = incomingEdges.filter((edge) => !store.edgeMap.has(edge.id));

    store.upsertNodes(incomingNodes);
    store.upsertEdges(incomingEdges);

    for (const node of newNodes) {
      graph.addItem("node", node);
    }
    for (const edge of newEdges) {
      graph.addItem("edge", edge);
    }

    if (newNodes.length > 0 || newEdges.length > 0) {
      graph.layout();
    }

    if (activeSeedNodeId) {
      const activeItem = graph.findById(activeSeedNodeId);
      if (activeItem) {
        applyNodeBaseStyle(activeItem);
      }
    }

    return {
      addedNodes: newNodes.length,
      addedEdges: newEdges.length
    };
  }

  graph.on("node:click", async (event) => {
    const model = event.item.getModel();

    if (!model || !model.id) {
      return;
    }

    markSeedNode(model.id);
    onNodeDetail?.(model);

    if (!fetchExpandData) {
      return;
    }

    if (store.inFlightSeeds.has(model.id)) {
      return;
    }

    try {
      store.inFlightSeeds.add(model.id);
      onExpandStart?.(model.id);

      const payload = await fetchExpandData(model.id);
      const merged = mergeGraphIncremental(payload);
      onExpandSuccess?.(model.id, merged);
    } catch (error) {
      onExpandError?.(model.id, error);
    } finally {
      store.inFlightSeeds.delete(model.id);
    }
  });

  graph.on("node:mouseenter", (event) => {
    const model = event.item.getModel();
    applyHoverEffect(event.item);
    onNodeHover(model);
  });

  graph.on("node:mouseleave", () => {
    resetHoverEffect();
    onNodeHover(null);
  });

  window.addEventListener("resize", () => {
    graph.changeSize(container.clientWidth, container.clientHeight);
  });

  ensureOverlay();

  return {
    mergeGraph(payload) {
      return mergeGraphIncremental(payload);
    },
    setSeedNode(nodeId) {
      if (!nodeId) {
        return;
      }
      markSeedNode(nodeId);
    },
    focusNode(nodeId) {
      if (!nodeId) {
        return;
      }
      const item = graph.findById(nodeId);
      if (item && graph.focusItem) {
        graph.focusItem(item, true, {
          easing: "easeCubic",
          duration: 400
        });
      }
    },
    clear() {
      activeSeedNodeId = null;
      store.clear();
      graph.changeData({ nodes: [], edges: [] });
      resetHoverEffect();
    }
  };
}
