export class GraphStore {
  constructor() {
    this.nodeMap = new Map();
    this.edgeMap = new Map();
    this.inFlightSeeds = new Set();
  }

  upsertNodes(nodes) {
    let added = 0;
    for (const node of nodes) {
      const existing = this.nodeMap.get(node.id);
      if (!existing) {
        added += 1;
      }
      if (existing && Number.isFinite(existing.x) && Number.isFinite(existing.y)) {
        node.x = existing.x;
        node.y = existing.y;
      }
      this.nodeMap.set(node.id, node);
    }
    return added;
  }

  upsertEdges(edges) {
    let added = 0;
    for (const edge of edges) {
      if (!this.edgeMap.has(edge.id)) {
        added += 1;
      }
      this.edgeMap.set(edge.id, edge);
    }
    return added;
  }

  snapshot() {
    return {
      nodes: Array.from(this.nodeMap.values()),
      edges: Array.from(this.edgeMap.values())
    };
  }

  clear() {
    this.nodeMap.clear();
    this.edgeMap.clear();
    this.inFlightSeeds.clear();
  }
}
