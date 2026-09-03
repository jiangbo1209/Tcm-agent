import request from "./request";

export function getFileUrlByUuid(fileUuid, mode = "view") {
  return request.get(`/files/${fileUuid}/download-url`, { params: { mode } }).then((res) => {
    const d = res.data;
    return { data: { url: d.url, file_name: d.original_name } };
  });
}
