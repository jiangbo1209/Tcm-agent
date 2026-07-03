import request from "./request";

export function expandGraph(seedId, limit = 10, depth = 1) {
  return request.get("/graph/expand", {
    params: { seed_id: seedId, limit, depth },
  });
}

export function getNodeDetail(nodeId) {
  return request.get("/graph/node-detail", { params: { node_id: nodeId } });
}

export function getDetailByFile(fileUuid, sourceType) {
  return request.get("/graph/node-detail", { params: { file_uuid: fileUuid, source_type: sourceType } });
}

export function searchGraph(q, page = 1, size = 10) {
  return request.get("/graph/search", { params: { q, page, size } });
}

export function getFileUrl(nodeId, mode = "view") {
  return request.get(`/graph/file-url/${nodeId}`, { params: { mode } });
}
