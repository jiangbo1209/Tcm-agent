import request from "./request";

export function fetchAdminList(table, page = 1, q = "") {
  return request.get(`/admin/${table}`, { params: { page, q } });
}

export function fetchAdminRecord(table, id) {
  return request.get(`/admin/${table}/${id}`);
}

export function updateAdminRecord(table, id, fields) {
  return request.put(`/admin/${table}/${id}`, { fields });
}
