import request from "./request";

export function smartSearch(query, searchType = "both", page = 1, size = 10, filters = {}) {
  return request.post("/search", { query, search_type: searchType, page, size, filters });
}

export function getSearchHistory(page = 1, size = 20) {
  return request.get("/search/history", { params: { page, size } });
}

export function getNodeDetail(nodeId) {
  return request.get("/graph/node-detail", { params: { node_id: nodeId } });
}
