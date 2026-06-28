import request from "./request";

export function getHistory(page = 1, size = 20) {
  return request.get("/history", { params: { page, size } });
}
