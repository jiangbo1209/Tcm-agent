import request from "./request";

/**
 * 数据标注 API 封装（标注员子集 + 少量管理端只读接口）。
 *
 * 端点契约对齐 UI/backend/app/routers/annotation.py 与 annotation_admin.py：
 * - claim 响应：{ task_id, count, deadline_at, table_name }
 * - 所有端点受 ANNOTATION_ENABLED 总闸保护，未开启时统一返回 503。
 *
 * ⚠️ /my/task 与 /my/rework 由后端 T7 提供，落地前调用会得到 404；
 *   调用方（AnnotationWorkbench.vue）需按“无数据”降级处理，不得中断页面。
 */

/** 标注员领取任务：POST /api/annotation/tasks/claim */
export function claimTask() {
  // 后端 ClaimRequest 允许空体，传 {} 保留扩展位
  return request.post("/annotation/tasks/claim", {});
}

/**
 * 查询当前进行中任务：GET /api/annotation/my/task
 * ⚠️ T7 落地前该端点不存在（404）。工作台将任何错误视为“无进行中任务”，
 * 回退展示领取面板；T7 接入真实数据后无需改动本封装。
 */
export function getMyTask() {
  return request.get("/annotation/my/task");
}

/**
 * 查询待返工数量：GET /api/annotation/my/rework
 * ⚠️ T7 落地前该端点不存在（404）。轮询失败时返工徽标直接隐藏。
 */
export function getMyRework() {
  return request.get("/annotation/my/rework");
}

/**
 * 保存条目草稿：PUT /api/annotation/items/{itemId}/draft
 * @param {string|number} itemId 条目 ID
 * @param {object} proposedFields 字段级修改提案；请求体形状以 T8 后端契约为准
 */
export function draftItem(itemId, proposedFields) {
  return request.put(`/annotation/items/${itemId}/draft`, {
    proposed_fields: proposedFields,
  });
}

/** 提交任务：POST /api/annotation/tasks/{taskId}/submit */
export function submitTask(taskId) {
  return request.post(`/annotation/tasks/${taskId}/submit`);
}

/**
 * 任务池列表（管理端只读）：GET /api/annotation/admin/pools
 * 仅管理员可用；普通标注员调用会得到 403，由调用方自行处理。
 */
export function listPools() {
  return request.get("/annotation/admin/pools");
}
