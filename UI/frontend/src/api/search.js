import request from "./request";

export function smartSearch(query, searchType = "both", page = 1, size = 10) {
  return request.post("/search", { query, search_type: searchType, page, size });
}

export function getSearchHistory(page = 1, size = 20) {
  return request.get("/search/history", { params: { page, size } });
}
