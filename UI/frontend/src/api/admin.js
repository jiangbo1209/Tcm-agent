import request from "./request";

export function fetchAdminList(table, { page = 1, q = "", crawlStatus, yearMin, yearMax, abstractAnomaly } = {}) {
  const params = { page, q };
  if (crawlStatus) params.crawl_status = crawlStatus;
  if (yearMin != null) params.year_min = yearMin;
  if (yearMax != null) params.year_max = yearMax;
  if (abstractAnomaly) params.abstract_anomaly = true;
  return request.get(`/admin/${table}`, { params });
}

export function fetchAdminRecord(table, id) {
  return request.get(`/admin/${table}/${id}`);
}

export function updateAdminRecord(table, id, fields) {
  return request.put(`/admin/${table}/${id}`, { fields });
}

export function fetchFileUrl(fileUuid, sourceType = "paper") {
  return request.get("/graph/file-url-by-uuid", {
    params: { file_uuid: fileUuid, source_type: sourceType, mode: "view" },
  });
}
