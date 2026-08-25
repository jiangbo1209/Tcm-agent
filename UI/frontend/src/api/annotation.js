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
 * 查询当前任务条目明细：GET /api/annotation/my/task/detail
 *
 * ⚠️ 后端缺口：该端点尚未提供（后续 todo 落地），当前调用会得到 404。
 * 工作台把任何错误一律降级为“空条目列表 + 条目接口尚未就绪”提示，
 * 绝不伪造数据；后端就绪后本封装无需改动。
 * 预期响应形状（宽松兼容）：{ items: [...] } 或裸数组，元素含
 * item_id/table_name/record_id/status(+record/submission/editable_fields)。
 */
export function getMyTaskDetail() {
  return request.get("/annotation/my/task/detail");
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
 * 数组元素：{ id, table_name, status, priority, deadline_days,
 *            total_items, remaining_items, created_at }
 */
export function listPools() {
  return request.get("/annotation/admin/pools");
}

/**
 * 建池预览（管理端，零写入）：POST /api/annotation/admin/pools/preview
 * @param {{ table_name: string, q?: string|null, crawl_status?: string|null,
 *           year_min?: number|null, year_max?: number|null,
 *           include_annotated?: boolean, page?: number, page_size?: number }} payload
 * @returns {Promise<{ total_matched: number, eligible: number,
 *           page: number, page_size: number,
 *           items: Array<{ record_id: number, title: string, crawl_status: string,
 *                           pub_year: string|null, eligible: boolean,
 *                           blocked: null|string }> }>}
 */
export function previewPool(payload) {
  return request.post("/annotation/admin/pools/preview", payload);
}

/**
 * 按筛选快照建池：POST /api/annotation/admin/pools
 * 响应：{ pool_id, total, ... , shortfall? }；shortfall>0 表示有命中记录
 * 因被占用/已完成标注未能入池。空候选集返回 400。
 */
export function createPool(payload) {
  return request.post("/annotation/admin/pools", payload);
}

/**
 * 调整池优先级/状态：PATCH /api/annotation/admin/pools/{poolId}
 * @param {number|string} poolId
 * @param {{ priority?: number, status?: "paused"|"closed" }} payload
 */
export function updatePool(poolId, payload) {
  return request.patch(`/annotation/admin/pools/${poolId}`, payload);
}

/**
 * 删除已关闭的任务池：DELETE /api/annotation/admin/pools/{poolId}
 * 仅 closed 状态的池可删除；非 closed 返回 409（detail="仅已关闭的任务池可删除"），
 * 不存在返回 404。删除后池内未领取的条目将回到候选空间。
 * @param {number|string} poolId
 */
export function deletePool(poolId) {
  return request.delete(`/annotation/admin/pools/${poolId}`);
}

/**
 * 管理员代派：POST /api/annotation/admin/tasks/assign
 * body { pool_id, user_ids }；响应 { results: [{ user_id, ok, task_id?, count?, error? }] }
 */
export function assignTasks(poolId, userIds) {
  return request.post("/annotation/admin/tasks/assign", {
    pool_id: poolId,
    user_ids: userIds,
  });
}

/**
 * 复核队列（按任务分组）：GET /api/annotation/admin/review/queue?status=
 * @param {"pending"|"expired"} status 待复核（默认）或基准冲突归档
 * 数组元素：{ task_id, annotator_username, table_name, count, submitted_at,
 *            items: [{ submission_id, item_id, record_id, current_values,
 *                      proposed_fields, base_updated_at, core_missing? }] }
 */
export function reviewQueue(status = "pending") {
  return request.get("/annotation/admin/review/queue", { params: { status } });
}

/**
 * 逐条批准：POST /api/annotation/admin/review/{submissionId}/approve
 * 响应 { submission_id, item_id, record_id, status }；
 * status ∈ {"approved", "expired"}——expired 表示基准冲突已归档进返工箱，不报错。
 */
export function approveSubmission(submissionId) {
  return request.post(`/annotation/admin/review/${submissionId}/approve`);
}

/**
 * 逐条驳回：POST /api/annotation/admin/review/{submissionId}/reject body { comment }
 * 意见必填（后端空串返回 400）；条目带意见进入返工箱。
 */
export function rejectSubmission(submissionId, comment) {
  return request.post(`/annotation/admin/review/${submissionId}/reject`, {
    comment,
  });
}

/* ═══════════════ 管理端看板 / 导出 / 审计日志（T17） ═══════════════ */

/**
 * 仪表盘聚合（管理端）：GET /api/annotation/admin/stats
 * 响应 { pools: [...], coverage: { lit|case|guideline: { annotated, total } },
 *        users: [{ user_id, username, completed, rejected_rate,
 *                  pending_rework, in_progress }] }
 */
export function dashboardStats() {
  return request.get("/annotation/admin/stats");
}

/**
 * 工作量明细 CSV 导出（管理端）：GET /api/annotation/admin/export.csv
 * @param {{ user_id?: number, pool_id?: number, date_from?: string, date_to?: string }} params
 * 全部可选；responseType 为 blob，调用方用 URL.createObjectURL 落盘下载
 * （后端 Content-Disposition 固定文件名 workload.csv）。
 */
export function exportCsv(params = {}) {
  return request.get("/annotation/admin/export.csv", {
    params,
    responseType: "blob",
  });
}

/**
 * 分页检索审计日志（管理端）：GET /api/annotation/admin/logs
 * @param {{ table_name?: string, record_id?: number, actor_id?: number,
 *           action?: string, date_from?: string, date_to?: string,
 *           page?: number, page_size?: number }} params 全部可选
 * 响应 { total, page, page_size, items: [{ id, table_name, record_id,
 *          actor_id, username, action, old_fields, new_fields,
 *          submission_id, created_at }] }；id 倒序。
 */
export function queryLogs(params = {}) {
  return request.get("/annotation/admin/logs", { params });
}

/**
 * 一键回滚（管理端）：POST /api/annotation/admin/logs/{logId}/rollback
 * 反向应用源日志 old_fields 并追加一条 rollback 审计行；
 * 响应 { log_id, record_id, table_name, restored_fields }；
 * 404 缺失 / 400 无可回滚字段 / 409 乐观锁冲突。
 */
export function rollbackLog(logId) {
  return request.post(`/annotation/admin/logs/${logId}/rollback`);
}
