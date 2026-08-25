<template>
  <div class="admin-page">
    <div class="admin-header">
      <h1>数据标注管理</h1>
    </div>

    <div class="mgmt-tabs">
      <button
        v-for="tab in TABS"
        :key="tab.key"
        class="mgmt-tab"
        :class="{ 'mgmt-tab-active': activeTab === tab.key }"
        :data-testid="tab.testid"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ═══════════ 任务池 ═══════════ -->
    <template v-if="activeTab === 'pools'">
      <!-- 任务池子页签 -->
      <div class="pool-subtabs">
        <button
          v-for="st in POOL_SUB_TABS"
          :key="st.key"
          class="pool-subtab"
          :class="{ 'pool-subtab-active': poolSubTab === st.key }"
          @click="poolSubTab = st.key"
        >
          {{ st.label }}
        </button>
      </div>

      <!-- 建池向导 -->
      <div v-if="poolSubTab === 'create'" class="wizard-card">
        <div class="wizard-header" @click="wizardOpen = !wizardOpen">
          <h2>建池向导</h2>
          <button class="btn-sm btn-wizard-toggle" type="button">
            {{ wizardOpen ? "收起 ▲" : "展开 ▼" }}
          </button>
        </div>
        <div v-show="wizardOpen" class="wizard-body">
          <div class="wizard-grid">
            <div class="form-field">
              <label>表类型</label>
              <select v-model="wizard.table_name">
                <option value="lit">文献元数据</option>
                <option value="case">病案元数据</option>
                <option value="guideline">指南元数据</option>
              </select>
            </div>
            <div class="form-field">
              <label>搜索词</label>
              <input v-model="wizard.q" type="text" placeholder="标题 / 关键词等，留空不过滤" />
            </div>
            <div class="form-field">
              <label>爬取状态</label>
              <select v-model="wizard.crawl_status">
                <option value="">全部</option>
                <option value="success">成功</option>
                <option value="partial">部分成功</option>
                <option value="failed">失败</option>
              </select>
            </div>
            <div class="form-field">
              <label>年份区间</label>
              <div class="year-range">
                <input v-model.number="wizard.year_min" type="number" placeholder="起始年份" />
                <span class="year-sep">—</span>
                <input v-model.number="wizard.year_max" type="number" placeholder="截止年份" />
              </div>
            </div>
            <div class="form-field">
              <label>截止天数</label>
              <input v-model.number="wizard.deadline_days" type="number" min="1" placeholder="留空使用全局默认" />
            </div>  
            <div class="form-field wiz-toggle-field">
              <label class="wiz-toggle-label">
                <input v-model="includeAnnotated" type="checkbox" class="wiz-checkbox" />
                <span>包含已完成标注</span>
              </label>
            </div>
          </div>
          <div class="wizard-actions">
            <button class="btn-create" :disabled="previewing" @click="handlePreview">
              {{ previewing ? "预览中..." : "预览" }}
            </button>
            <button class="btn-create btn-select-all" :class="{ 'btn-select-all-active': selectAllMode }" @click="toggleSelectAllMode">
              {{ selectAllMode ? "已选全部命中 · 取消全选" : "勾选所有命中" }}
            </button>
            <button class="btn-create btn-confirm" :disabled="!canCreate || creating" @click="handleCreatePool">
              {{ creating ? "建池中..." : (selectAllMode ? "确认建池（全部命中）" : `确认建池（${selectedRecordIds.size} 条）`) }}
            </button>
          </div>
          <p v-if="previewText" class="preview-result" data-testid="pool-preview">{{ previewText }}</p>

          <!-- 候选明细表 -->
          <div v-if="previewResult" class="wiz-preview">
            <div class="wiz-preview-toolbar">
              <button class="btn-sm btn-assign" :disabled="allEligibleOnPage.length === 0" @click="toggleSelectAll">
                {{ isAllSelected() ? "取消本页全选" : "全选本页" }}
              </button>
              <span class="wiz-selected-count">已选 <strong>{{ selectedRecordIds.size }}</strong> 条</span>
            </div>
            <div class="wiz-table-wrap">
              <table class="pool-table wiz-preview-table">
                <thead>
                  <tr>
                    <th class="wiz-col-check">
                      <input
                        type="checkbox"
                        class="wiz-checkbox"
                        :checked="isAllSelected()"
                        :disabled="allEligibleOnPage.length === 0"
                        @change="toggleSelectAll"
                      />
                    </th>
                    <th class="wiz-col-id">#ID</th>
                    <th>标题</th>
                    <th class="wiz-col-status">数据状态</th>
                    <th class="wiz-col-year">年份</th>
                    <th class="wiz-col-pool">入池状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="item in previewResult.items"
                    :key="item.record_id"
                    class="wiz-row"
                    :class="{ 'wiz-row-disabled': !item.eligible }"
                  >
                    <td class="wiz-col-check">
                      <input
                        type="checkbox"
                        class="wiz-checkbox"
                        :checked="selectedRecordIds.has(item.record_id)"
                        :disabled="!item.eligible"
                        @change="toggleRecord(item.record_id, item.eligible)"
                      />
                    </td>
                    <td class="wiz-col-id">{{ item.record_id }}</td>
                    <td class="wiz-col-title" :title="item.title">{{ item.title }}</td>
                    <td class="wiz-col-status">
                      <span class="badge" :class="crawlStatusBadge(item.crawl_status)">{{ crawlStatusLabel(item.crawl_status) }}</span>
                    </td>
                    <td class="wiz-col-year">{{ item.pub_year || "—" }}</td>
                    <td class="wiz-col-pool">
                      <span v-if="item.eligible" class="badge badge-eligible">可入池</span>
                      <span v-else class="badge badge-blocked">{{ blockedLabel(item.blocked) }}</span>
                    </td>
                  </tr>
                  <tr v-if="!previewResult.items || previewResult.items.length === 0">
                    <td colspan="6" class="empty-row">无匹配记录</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="wiz-pager">
              <button
                class="btn-sm"
                :disabled="previewPage <= 1 || previewing"
                @click="goPreviewPage(previewPage - 1)"
              >上一页</button>
              <span class="pager-info">第 {{ previewPage }} / {{ previewPageCount }} 页</span>
              <button
                class="btn-sm"
                :disabled="previewPage >= previewPageCount || previewing"
                @click="goPreviewPage(previewPage + 1)"
              >下一页</button>
            </div>
          </div>

          <p v-if="wizardError" class="form-error">{{ wizardError }}</p>
        </div>
      </div>

      <!-- 池列表 -->
      <template v-if="poolSubTab === 'pools'">
      <div v-if="poolsLoading" class="loading">加载中...</div>
      <div v-else class="table-wrap">
        <table class="pool-table" data-testid="pool-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>表类型</th>
              <th>状态</th>
              <th>优先级</th>
              <th>余量</th>
              <th>截止天数</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pool in pools" :key="pool.id">
              <td>{{ pool.id }}</td>
              <td>{{ tableLabel(pool.table_name) }}</td>
              <td>
                <span class="badge" :class="statusMeta(pool.status).cls">
                  {{ statusMeta(pool.status).label }}
                </span>
              </td>
              <td class="cell-priority">{{ pool.priority }}</td>
              <td>
                <div class="progress-cell">
                  <div class="progress-track">
                    <div class="progress-fill" :style="{ width: progressPct(pool) + '%' }"></div>
                  </div>
                  <span class="progress-text">{{ pool.remaining_items }}/{{ pool.total_items }}</span>
                </div>
              </td>
              <td class="cell-time">{{ pool.deadline_days ?? "默认" }}</td>
              <td class="cell-time">{{ formatDate(pool.created_at) }}</td>
              <td class="cell-actions">
                <button class="btn-sm btn-assign" @click="openAssign(pool)">指派</button>
                <button
                  v-if="pool.status === 'active'"
                  class="btn-sm btn-toggle"
                  @click="pausePool(pool)"
                >
                  暂停
                </button>
                <button v-if="pool.status !== 'closed'" class="btn-sm btn-delete" @click="closePool(pool)">
                  关闭
                </button>
                <button v-if="pool.status === 'closed'" class="btn-sm btn-delete" @click="handleDeletePool(pool)">
                  删除
                </button>
                <button class="btn-sm btn-priority" @click="changePriority(pool, 1)">优先级+1</button>
                <button class="btn-sm btn-priority" @click="changePriority(pool, -1)">优先级-1</button>
              </td>
            </tr>
            <tr v-if="pools.length === 0">
              <td colspan="8" class="empty-row">暂无任务池</td>
            </tr>
          </tbody>
        </table>
      </div>
      </template>

    </template>

    <!-- ═══════════ 复核队列 ═══════════ -->
    <template v-else-if="activeTab === 'review'">
      <!-- 工具行 -->
      <div class="review-toolbar">
        <label class="review-select-all">
          <input
            type="checkbox"
            class="wiz-checkbox"
            :checked="isReviewAllSelected"
            :disabled="!reviewSelectableItems.length"
            @change="toggleReviewSelectAll"
          />
          <span>全选本页</span>
        </label>
        <button
          class="btn-sm btn-review-approve"
          :disabled="!selectedReviewIds.size || batchActing"
          @click="handleBatchApprove"
        >
          批量通过
        </button>
        <button
          class="btn-sm btn-review-reject"
          :disabled="!selectedReviewIds.size || batchActing"
          @click="openBatchReject"
        >
          批量驳回
        </button>
        <span class="review-count">
          已选 <strong>{{ selectedReviewIds.size }}</strong> / 本页 {{ reviewSelectableItems.length }} · 共 {{ reviewTotal }} 条待复核
        </span>
        <div class="review-pager">
          <button
            class="btn-sm"
            :disabled="reviewPage <= 1 || reviewLoading"
            @click="goReviewPage(reviewPage - 1)"
          >上一页</button>
          <span class="pager-info">第 {{ reviewPage }} / {{ reviewPageCount }} 页</span>
          <button
            class="btn-sm"
            :disabled="reviewPage >= reviewPageCount || reviewLoading"
            @click="goReviewPage(reviewPage + 1)"
          >下一页</button>
        </div>
      </div>

      <div v-if="reviewLoading" class="loading">加载中...</div>
      <div v-else-if="reviewItems.length === 0" class="placeholder-card">
        暂无待复核提交
      </div>
      <div v-else class="review-flat-list" data-testid="review-flat-list">
        <table class="pool-table review-table" data-testid="review-table">
          <thead>
            <tr>
              <th class="rev-col-check"></th>
              <th class="rev-col-id">#记录ID</th>
              <th>标注员</th>
              <th>表类型</th>
              <th>提交值摘要</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="item in reviewItems" :key="item.submission_id">
              <tr
                class="review-row"
                :class="{
                  'review-row-core-missing': item.core_missing,
                  'review-row-selected': selectedReviewIds.has(item.submission_id),
                }"
              >
                <td class="rev-col-check">
                  <input
                    type="checkbox"
                    class="wiz-checkbox"
                    :checked="selectedReviewIds.has(item.submission_id)"
                    @change="toggleReviewItem(item.submission_id)"
                  />
                </td>
                <td class="rev-col-id">#{{ item.record_id }}</td>
                <td>{{ item.annotator_username || "—" }}</td>
                <td>{{ tableLabel(item.table_name) }}</td>
                <td class="rev-summary">
                  <span v-if="item.core_missing" class="core-missing-badge">核心缺失</span>
                  <span v-if="!hasDiff(item)" class="badge badge-no-diff">无需修改</span>
                  <span v-else class="badge badge-has-diff">{{ Object.keys(item.proposed_fields || {}).length }} 字段</span>
                </td>
                <td>
                  <span class="badge badge-pending">待复核</span>
                </td>
                <td class="cell-actions">
                  <button
                    class="btn-sm btn-review-approve"
                    :disabled="actingId === item.submission_id || item.core_missing"
                    @click="handleSingleApprove(item)"
                  >通过</button>
                  <button
                    class="btn-sm btn-review-reject"
                    :disabled="actingId === item.submission_id"
                    @click="openReject(item)"
                  >驳回</button>
                  <button
                    class="btn-sm btn-review-expand"
                    @click="toggleReviewExpand(item.submission_id)"
                  >{{ expandedReviewId === item.submission_id ? "收起" : "展开" }}</button>
                </td>
              </tr>
              <!-- 展开双栏对照 -->
              <tr v-if="expandedReviewId === item.submission_id" class="review-expand-row">
                <td colspan="7" class="review-expand-cell">
                  <div class="diff-legend"><span class="diff-legend-mark">■</span> 高亮 = 标注员修改的字段</div>
                  <div class="diff-grid">
                    <div class="diff-col diff-col-current">
                      <div class="diff-col-title">当前值</div>
                      <div v-for="field in diffFields(item)" :key="'c-' + field" class="diff-row">
                        <span class="diff-key">{{ field }}</span>
                        <span class="diff-val">{{ formatValue(item.current_values?.[field]) }}</span>
                      </div>
                    </div>
                    <div class="diff-col diff-col-proposed">
                      <div class="diff-col-title">提交值</div>
                      <div v-for="field in diffFields(item)" :key="'p-' + field" class="diff-row">
                        <span class="diff-key">{{ field }}</span>
                        <span
                          class="diff-val"
                          :class="{
                            'diff-changed':
                              formatValue(item.proposed_fields?.[field]) !==
                              formatValue(item.current_values?.[field]),
                          }"
                        >{{ formatValue(item.proposed_fields?.[field]) }}</span>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ═══════════ 看板 ═══════════ -->
    <template v-else-if="activeTab === 'board'">
      <div v-if="boardLoading" class="loading">加载中...</div>
      <template v-else>
        <div class="coverage-grid">
          <div v-for="t in COVERAGE_TABLES" :key="t.key" class="coverage-card">
            <h3>{{ t.label }}</h3>
            <p class="coverage-num">已标注 {{ coverageOf(t.key).annotated }} / 共 {{ coverageOf(t.key).total }}</p>
            <div class="progress-track coverage-track">
              <div class="progress-fill" :style="{ width: coveragePct(t.key) + '%' }"></div>
            </div>
          </div>
        </div>

        <h2 class="board-section-title">任务池余量</h2>
        <div v-if="stats.pools.length === 0" class="placeholder-card">暂无任务池</div>
        <div v-else class="table-wrap">
          <table class="pool-table">
            <thead>
              <tr>
                <th>表类型</th>
                <th>状态</th>
                <th>余量</th>
                <th>优先级</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pool in stats.pools" :key="pool.id">
                <td>{{ tableLabel(pool.table_name) }}</td>
                <td>
                  <span class="badge" :class="statusMeta(pool.status).cls">
                    {{ statusMeta(pool.status).label }}
                  </span>
                </td>
                <td>
                  <div class="progress-cell">
                    <div class="progress-track">
                      <div class="progress-fill" :style="{ width: poolProgressPct(pool) + '%' }"></div>
                    </div>
                    <span class="progress-text">{{ pool.remaining_items }}/{{ pool.total_items }}</span>
                  </div>
                </td>
                <td class="cell-priority">{{ pool.priority }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h2 class="board-section-title">标注员工作量</h2>
        <div class="table-wrap">
          <table class="pool-table" data-testid="board-users">
            <thead>
              <tr>
                <th>标注员</th>
                <th>已完成</th>
                <th>驳回率</th>
                <th>待返工</th>
                <th>在办任务</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in stats.users" :key="u.user_id">
                <td>{{ u.username }}</td>
                <td>{{ u.completed }}</td>
                <td>
                  <span :class="'rate-' + rateLevel(u.rejected_rate)">{{ formatRate(u.rejected_rate) }}</span>
                </td>
                <td>{{ u.pending_rework }}</td>
                <td>{{ u.in_progress ? "是" : "否" }}</td>
              </tr>
              <tr v-if="stats.users.length === 0">
                <td colspan="5" class="empty-row">暂无标注员</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>

    <!-- ═══════════ 导出 ═══════════ -->
    <template v-else-if="activeTab === 'export'">
      <div class="wizard-card">
        <div class="wizard-body export-body">
          <div class="wizard-grid">
            <div class="form-field">
              <label>标注员</label>
              <select v-model="exportFilter.user_id">
                <option :value="null">全部</option>
                <option v-for="u in annotators" :key="u.id" :value="u.id">{{ u.username }}</option>
              </select>
            </div>
            <div class="form-field">
              <label>任务池</label>
              <select v-model="exportFilter.pool_id">
                <option :value="null">全部</option>
                <option v-for="p in pools" :key="p.id" :value="p.id">
                  #{{ p.id }} {{ tableLabel(p.table_name) }}
                </option>
              </select>
            </div>
            <div class="form-field">
              <label>开始时间</label>
              <input v-model="exportFilter.date_from" type="datetime-local" />
            </div>
            <div class="form-field">
              <label>结束时间</label>
              <input v-model="exportFilter.date_to" type="datetime-local" />
            </div>
          </div>
          <div class="wizard-actions">
            <button class="btn-create" :disabled="exporting" @click="handleExportCsv">
              {{ exporting ? "导出中..." : "导出 CSV" }}
            </button>
          </div>
          <p v-if="exportError" class="form-error">{{ exportError }}</p>
        </div>
      </div>
    </template>

    <!-- ═══════════ 回滚日志 ═══════════ -->
    <template v-else-if="activeTab === 'rollback'">
      <div class="log-filters">
        <select v-model="logFilters.table_name" class="filter-select" @change="resetAndLoadLogs">
          <option value="">全部表</option>
          <option value="lit">文献元数据</option>
          <option value="case">病案元数据</option>
          <option value="guideline">指南元数据</option>
        </select>
        <select v-model="logFilters.action" class="filter-select" @change="resetAndLoadLogs">
          <option value="">全部动作</option>
          <option v-for="a in LOG_ACTIONS" :key="a" :value="a">{{ actionMeta(a).label }}</option>
        </select>
        <input
          v-model="logFilters.record_id"
          type="number"
          placeholder="记录 ID"
          class="filter-input"
          @keyup.enter="resetAndLoadLogs"
        />
        <button class="btn-sm btn-assign" @click="resetAndLoadLogs">查询</button>
      </div>

      <div v-if="logsLoading" class="loading">加载中...</div>
      <template v-else>
        <div class="table-wrap">
          <table class="pool-table logs-table" data-testid="logs-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>时间</th>
                <th>操作人</th>
                <th>表</th>
                <th>记录</th>
                <th>动作</th>
                <th>变更摘要</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in logs" :key="log.id">
                <td>{{ log.id }}</td>
                <td class="cell-time">{{ formatDate(log.created_at) }}</td>
                <td>{{ log.username || "—" }}</td>
                <td>{{ tableLabel(log.table_name) }}</td>
                <td>#{{ log.record_id }}</td>
                <td>
                  <span class="badge" :class="actionMeta(log.action).cls">
                    {{ actionMeta(log.action).label }}
                  </span>
                </td>
                <td class="cell-summary">{{ changeSummary(log) }}</td>
                <td class="cell-actions">
                  <button
                    v-if="hasOldFields(log)"
                    class="btn-sm btn-toggle"
                    :disabled="rollingBackId === log.id"
                    @click="handleRollback(log)"
                  >
                    {{ rollingBackId === log.id ? "回滚中..." : "回滚" }}
                  </button>
                </td>
              </tr>
              <tr v-if="logs.length === 0">
                <td colspan="8" class="empty-row">暂无日志</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="pager">
          <button class="btn-sm" :disabled="logPage <= 1 || logsLoading" @click="goLogPage(logPage - 1)">
            上一页
          </button>
          <span class="pager-info">第 {{ logPage }} 页 · 共 {{ logTotal }} 条</span>
          <button
            class="btn-sm"
            :disabled="logPage >= logPageCount || logsLoading"
            @click="goLogPage(logPage + 1)"
          >
            下一页
          </button>
        </div>
      </template>
    </template>

    <div v-else class="placeholder-card">建设中</div>

    <!-- ═══════════ 指派对话框 ═══════════ -->
    <div v-if="assignTarget" class="modal-overlay" @click.self="closeAssign">
      <div class="modal-box" data-testid="assign-dialog">
        <div class="modal-header">
          <h2>指派任务 — 池 #{{ assignTarget.id }}（{{ tableLabel(assignTarget.table_name) }}）</h2>
          <button class="modal-close" @click="closeAssign">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="annotatorsLoading" class="loading">加载标注员中...</div>
          <template v-else>
            <p class="annotator-hint">
              勾选要代派的标注员（每人随机抽取一批条目；余量 {{ assignTarget.remaining_items }}/{{ assignTarget.total_items }}）
            </p>
            <div v-if="annotators.length === 0" class="empty-hint">暂无可指派的标注员</div>
            <label v-for="u in annotators" :key="u.id" class="annotator-row">
              <input v-model="selectedUserIds" type="checkbox" :value="u.id" :disabled="!!assignResults" />
              <span class="annotator-name">{{ u.username }}</span>
              <span class="annotator-email">{{ u.email }}</span>
            </label>
          </template>

          <div v-if="assignError" class="form-error">{{ assignError }}</div>

          <div v-if="assignResults" class="assign-results">
            <h3>指派结果</h3>
            <p
              v-for="(r, idx) in assignResults"
              :key="idx"
              :class="r.ok ? 'result-ok' : 'result-fail'"
            >
              <template v-if="r.ok">✓ {{ userName(r.user_id) }}：已派 {{ r.count }} 条</template>
              <template v-else>✗ {{ userName(r.user_id) }}：{{ r.error }}</template>
            </p>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="closeAssign">{{ assignResults ? "关闭" : "取消" }}</button>
          <button
            v-if="!assignResults"
            class="btn-save"
            :disabled="assigning || selectedUserIds.length === 0"
            @click="confirmAssign"
          >
            {{ assigning ? "指派中..." : `确认指派（${selectedUserIds.length}）` }}
          </button>
        </div>
      </div>
    </div>

    <!-- ═══════════ 驳回对话框（单条 / 批量共用） ═══════════ -->
    <div v-if="rejectTarget || batchRejecting" class="modal-overlay" @click.self="closeReject">
      <div class="modal-box" data-testid="reject-dialog">
        <div class="modal-header">
          <h2 v-if="batchRejecting">批量驳回（{{ selectedReviewIds.size }} 条）</h2>
          <h2 v-else>驳回提交 #{{ rejectTarget?.submission_id }}（记录 #{{ rejectTarget?.record_id }}）</h2>
          <button class="modal-close" @click="closeReject">&times;</button>
        </div>
        <div class="modal-body">
          <p class="annotator-hint">驳回后选中的条目将带复核意见进入标注员返工箱。</p>
          <div class="form-field">
            <label>复核意见（必填）</label>
            <textarea
              v-model="rejectComment"
              rows="4"
              placeholder="请填写驳回原因，将反馈给标注员"
            ></textarea>
          </div>
          <div v-if="rejectError" class="form-error">{{ rejectError }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="closeReject">取消</button>
          <button
            class="btn-save btn-reject-confirm"
            :disabled="rejecting || !rejectComment.trim()"
            @click="confirmReject"
          >
            {{ rejecting ? "驳回中..." : "确认驳回" }}
          </button>
        </div>
      </div>
    </div>

    <!-- 全局提示 -->
    <transition name="toast-fade">
      <div v-if="toast.visible" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import {
  listPools,
  previewPool,
  createPool,
  updatePool,
  deletePool,
  assignTasks,
  reviewQueueFlat,
  approveSubmission,
  rejectSubmission,
  batchApprove,
  batchReject,
  dashboardStats,
  exportCsv,
  queryLogs,
  rollbackLog,
} from "../../api/annotation";
import { fetchUsers } from "../../api/users";

/* ───────── 页签 ───────── */
const TABS = [
  { key: "pools", label: "任务池", testid: "pools-tab" },
  { key: "review", label: "复核队列", testid: "review-tab" },
  { key: "board", label: "看板", testid: "board-tab" },
  { key: "export", label: "导出", testid: "export-tab" },
  { key: "rollback", label: "回滚", testid: "rollback-tab" },
];
const activeTab = ref("pools");

/* ───────── 任务池子页签 ───────── */
const POOL_SUB_TABS = [
  { key: "create", label: "新建任务" },
  { key: "pools", label: "进行中任务" },
];
const poolSubTab = ref("create");

/* ───────── 字典 ───────── */
const TABLE_LABELS = { lit: "文献元数据", case: "病案元数据", guideline: "指南元数据" };
const STATUS_META = {
  active: { label: "进行中", cls: "badge-active" },
  paused: { label: "已暂停", cls: "badge-paused" },
  closed: { label: "已关闭", cls: "badge-closed" },
};

function tableLabel(name) {
  return TABLE_LABELS[name] || name;
}
function statusMeta(status) {
  return STATUS_META[status] || { label: status, cls: "badge-closed" };
}
function formatDate(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 16);
}

/* ───────── 提示 toast ───────── */
const toast = ref({ visible: false, message: "", type: "success" });
let toastTimer = null;
function showToast(message, type = "success") {
  toast.value = { visible: true, message, type };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value.visible = false;
  }, 4000);
}

/* ───────── 建池向导 ───────── */
const PREVIEW_PAGE_SIZE = 20;

const wizardOpen = ref(true);
const wizard = ref({
  table_name: "lit",
  q: "",
  crawl_status: "",
  year_min: null,
  year_max: null,
  deadline_days: null,
});
const includeAnnotated = ref(false);
const previewing = ref(false);
const creating = ref(false);
const previewResult = ref(null); // { total_matched, eligible, page, page_size, items }
const selectedRecordIds = ref(new Set());
const selectAllMode = ref(false);
const previewPage = ref(1);
const wizardError = ref("");

// 任一筛选条件变化后旧预览失效，需重新预览才能建池
watch(
  () => [
    wizard.value.table_name,
    wizard.value.q,
    wizard.value.crawl_status,
    wizard.value.year_min,
    wizard.value.year_max,
    includeAnnotated.value,
  ],
  () => {
    previewResult.value = null;
    selectedRecordIds.value = new Set();
    selectAllMode.value = false;
    previewPage.value = 1;
  }
);

const previewText = computed(() => {
  if (!previewResult.value) return "";
  const { total_matched, eligible } = previewResult.value;
  let text = `命中 ${total_matched} 条，可入池 ${eligible} 条`;
  if (eligible < total_matched) {
    text += `（另有 ${total_matched - eligible} 条已被占用或已完成标注）`;
  }
  return text;
});

const previewPageCount = computed(() => {
  if (!previewResult.value) return 1;
  return Math.max(1, Math.ceil(previewResult.value.total_matched / (previewResult.value.page_size || PREVIEW_PAGE_SIZE)));
});

const canCreate = computed(() => selectedRecordIds.value.size > 0 || selectAllMode.value);

function numOrNull(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function filterPayload() {
  const w = wizard.value;
  return {
    table_name: w.table_name,
    q: String(w.q || "").trim() || null,
    crawl_status: w.crawl_status || null,
    year_min: numOrNull(w.year_min),
    year_max: numOrNull(w.year_max),
  };
}

async function handlePreview() {
  wizardError.value = "";
  previewing.value = true;
  selectedRecordIds.value = new Set();
  try {
    const payload = {
      ...filterPayload(),
      include_annotated: includeAnnotated.value,
    };
    const res = await previewPool(payload, {
      page: previewPage.value,
      page_size: PREVIEW_PAGE_SIZE,
    });
    previewResult.value = res.data;
  } catch (e) {
    previewResult.value = null;
    wizardError.value = e.response?.data?.detail || "预览失败";
  } finally {
    previewing.value = false;
  }
}

async function handleCreatePool() {
  if (!canCreate.value) return;
  wizardError.value = "";
  creating.value = true;
  try {
    const base = {
      ...filterPayload(),
      include_annotated: includeAnnotated.value,
      deadline_days: numOrNull(wizard.value.deadline_days),
    };
    // selectAllMode: 不传 record_ids，后端走筛选全量路径
    const payload = selectAllMode.value
      ? base
      : { ...base, record_ids: [...selectedRecordIds.value] };
    const res = await createPool(payload);
    const d = res.data || {};
    let msg = `建池成功：入池 ${d.total} 条`;
    if (d.shortfall > 0) msg += `，另有 ${d.shortfall} 条已被占用或已完成标注未能入池`;
    if (d.included_approved > 0) msg += `（含已完成标注 ${d.included_approved} 条）`;
    showToast(msg);
    previewResult.value = null;
    selectedRecordIds.value = new Set();
    selectAllMode.value = false;
    await loadPools();
  } catch (e) {
    wizardError.value = e.response?.data?.detail || "建池失败";
  } finally {
    creating.value = false;
  }
}

/* ── 预览勾选辅助 ── */
function toggleSelectAllMode() {
  if (selectAllMode.value) {
    // 取消全选
    selectAllMode.value = false;
  } else {
    // 勾选所有命中：清空逐条选中，启用全量模式
    selectedRecordIds.value = new Set();
    selectAllMode.value = true;
  }
}

function toggleRecord(recordId, eligible) {
  if (!eligible) return;
  const next = new Set(selectedRecordIds.value);
  if (next.has(recordId)) {
    next.delete(recordId);
  } else {
    next.add(recordId);
  }
  selectedRecordIds.value = next;
}

function toggleSelectAll() {
  const items = previewResult.value?.items || [];
  const next = new Set(selectedRecordIds.value);
  const eligibleIds = items.filter((i) => i.eligible).map((i) => i.record_id);
  const allSelected = eligibleIds.length > 0 && eligibleIds.every((id) => next.has(id));
  if (allSelected) {
    eligibleIds.forEach((id) => next.delete(id));
  } else {
    eligibleIds.forEach((id) => next.add(id));
  }
  selectedRecordIds.value = next;
}

function isAllSelected() {
  const items = previewResult.value?.items || [];
  const eligibleIds = items.filter((i) => i.eligible).map((i) => i.record_id);
  return eligibleIds.length > 0 && eligibleIds.every((id) => selectedRecordIds.value.has(id));
}

const allEligibleOnPage = computed(() => {
  const items = previewResult.value?.items || [];
  return items.filter((i) => i.eligible);
});

function goPreviewPage(page) {
  if (page < 1 || page > previewPageCount.value) return;
  selectedRecordIds.value = new Set();
  selectAllMode.value = false;
  previewPage.value = page;
  handlePreview();
}

function blockedLabel(blocked) {
  if (!blocked) return "";
  const map = { pooled: "已被占用", task: "任务进行中", approved: "已完成标注" };
  return map[blocked] || blocked;
}

function crawlStatusBadge(cls) {
  if (cls === "success") return "badge-crawl-success";
  if (cls === "partial") return "badge-crawl-partial";
  if (cls === "failed") return "badge-crawl-failed";
  return "badge-crawl-default";
}

function crawlStatusLabel(s) {
  if (s === "success") return "成功";
  if (s === "partial") return "部分";
  if (s === "failed") return "失败";
  return s || "—";
}

/* ───────── 池列表 ───────── */
const pools = ref([]);
const poolsLoading = ref(false);

async function loadPools() {
  poolsLoading.value = true;
  try {
    const res = await listPools();
    pools.value = Array.isArray(res.data) ? res.data : [];
  } catch (e) {
    console.error("Failed to load pools:", e);
  } finally {
    poolsLoading.value = false;
  }
}

function progressPct(pool) {
  if (!pool.total_items) return 0;
  return Math.min(100, Math.round((pool.remaining_items / pool.total_items) * 100));
}

async function changePriority(pool, delta) {
  try {
    await updatePool(pool.id, { priority: pool.priority + delta });
    await loadPools();
  } catch (e) {
    alert(e.response?.data?.detail || "调整优先级失败");
    await loadPools();
  }
}

async function pausePool(pool) {
  try {
    await updatePool(pool.id, { status: "paused" });
    await loadPools();
  } catch (e) {
    alert(e.response?.data?.detail || "暂停失败");
    await loadPools();
  }
}

async function closePool(pool) {
  if (!confirm(`确定关闭任务池 #${pool.id} 吗？关闭后不再参与派发。`)) return;
  try {
    await updatePool(pool.id, { status: "closed" });
    await loadPools();
  } catch (e) {
    alert(e.response?.data?.detail || "关闭失败");
    await loadPools();
  }
}

async function handleDeletePool(pool) {
  if (!confirm(`删除任务池 #${pool.id}？未领取的条目将回到候选空间。`)) return;
  try {
    await deletePool(pool.id);
    showToast(`任务池 #${pool.id} 已删除`);
    await loadPools();
  } catch (e) {
    alert(e.response?.data?.detail || "删除失败");
    await loadPools();
  }
}

/* ───────── 指派对话框 ───────── */
const assignTarget = ref(null); // 当前指派的池行
const annotators = ref([]);
const annotatorsLoading = ref(false);
const selectedUserIds = ref([]);
const assigning = ref(false);
const assignResults = ref(null); // 后端逐用户结果数组
const assignError = ref("");

function userName(userId) {
  const u = annotators.value.find((a) => a.id === userId);
  return u ? u.username : `用户#${userId}`;
}

async function openAssign(pool) {
  assignTarget.value = pool;
  selectedUserIds.value = [];
  assignResults.value = null;
  assignError.value = "";
  annotatorsLoading.value = true;
  try {
    const res = await fetchUsers();
    annotators.value = (res.data.users || []).filter((u) => u.role === "annotator");
  } catch (e) {
    annotators.value = [];
    assignError.value = e.response?.data?.detail || "加载标注员失败";
  } finally {
    annotatorsLoading.value = false;
  }
}

function closeAssign() {
  assignTarget.value = null;
  assignResults.value = null;
  assignError.value = "";
}

async function confirmAssign() {
  if (!assignTarget.value || selectedUserIds.value.length === 0) return;
  assignError.value = "";
  assigning.value = true;
  try {
    const res = await assignTasks(assignTarget.value.id, [...selectedUserIds.value]);
    assignResults.value = res.data?.results || [];
    selectedUserIds.value = [];
    await loadPools(); // 代派消耗余量，刷新列表
  } catch (e) {
    assignError.value = e.response?.data?.detail || "指派失败";
  } finally {
    assigning.value = false;
  }
}

/* ───────── 复核队列（扁平分页） ───────── */
const REVIEW_PAGE_SIZE = 20;
const reviewItems = ref([]);
const reviewTotal = ref(0);
const reviewPage = ref(1);
const reviewLoading = ref(false);
const selectedReviewIds = ref(new Set());
const expandedReviewId = ref(null);
const actingId = ref(null);
const batchActing = ref(false);

const reviewPageCount = computed(() => Math.max(1, Math.ceil(reviewTotal.value / REVIEW_PAGE_SIZE)));

const reviewSelectableItems = computed(() => reviewItems.value.filter((i) => !i.core_missing));

const isReviewAllSelected = computed(() => {
  const sel = reviewSelectableItems.value;
  return sel.length > 0 && sel.every((i) => selectedReviewIds.value.has(i.submission_id));
});

async function loadReviewQueue() {
  reviewLoading.value = true;
  try {
    const res = await reviewQueueFlat({ page: reviewPage.value, page_size: REVIEW_PAGE_SIZE });
    const d = res.data || {};
    reviewItems.value = Array.isArray(d.items) ? d.items : [];
    reviewTotal.value = d.total ?? 0;
    selectedReviewIds.value = new Set();
    expandedReviewId.value = null;
  } catch (e) {
    reviewItems.value = [];
    reviewTotal.value = 0;
    showToast(e.response?.data?.detail || "加载复核队列失败", "error");
  } finally {
    reviewLoading.value = false;
  }
}

function goReviewPage(p) {
  if (p < 1 || p > reviewPageCount.value) return;
  reviewPage.value = p;
  loadReviewQueue();
}

function toggleReviewItem(sid) {
  const next = new Set(selectedReviewIds.value);
  if (next.has(sid)) next.delete(sid);
  else next.add(sid);
  selectedReviewIds.value = next;
}

function toggleReviewSelectAll() {
  const sel = reviewSelectableItems.value;
  const allSel = isReviewAllSelected.value;
  const next = new Set(selectedReviewIds.value);
  for (const i of sel) {
    if (allSel) next.delete(i.submission_id);
    else next.add(i.submission_id);
  }
  selectedReviewIds.value = next;
}

function toggleReviewExpand(sid) {
  expandedReviewId.value = expandedReviewId.value === sid ? null : sid;
}

// hasDiff / diffFields / formatValue —— 精确保留原有实现
function hasDiff(entry) {
  const p = entry.proposed_fields;
  return !!p && typeof p === "object" && Object.keys(p).length > 0;
}

function diffFields(entry) {
  const proposed = Object.keys(entry.proposed_fields || {});
  const current = Object.keys(entry.current_values || {});
  const rest = current.filter((k) => !proposed.includes(k));
  return [...proposed, ...rest];
}

function formatValue(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.length ? v.join("、") : "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

async function handleSingleApprove(entry) {
  actingId.value = entry.submission_id;
  try {
    const res = await approveSubmission(entry.submission_id);
    if (res.data?.status === "expired") {
      showToast(`提交 #${entry.submission_id} 基准冲突，已归档为过期`, "error");
    } else {
      showToast(`提交 #${entry.submission_id} 已通过`);
    }
    removeReviewItem(entry.submission_id);
  } catch (e) {
    showToast(e.response?.data?.detail || "通过失败", "error");
  } finally {
    actingId.value = null;
  }
}

function removeReviewItem(sid) {
  const idx = reviewItems.value.findIndex((i) => i.submission_id === sid);
  if (idx !== -1) {
    reviewItems.value.splice(idx, 1);
    reviewTotal.value = Math.max(0, reviewTotal.value - 1);
    selectedReviewIds.value.delete(sid);
    if (expandedReviewId.value === sid) expandedReviewId.value = null;
  }
}

/* ─── 批量通过 ─── */
async function handleBatchApprove() {
  const ids = [...selectedReviewIds.value];
  if (!ids.length) return;
  if (!confirm(`确认批量通过 ${ids.length} 条提交？`)) return;
  batchActing.value = true;
  try {
    const res = await batchApprove(ids);
    const d = res.data || {};
    const s = d.summary || d;
    showToast(
      `通过 ${s.approved ?? 0} · 过期 ${s.expired ?? 0} · 异常 ${s.error ?? 0}`
    );
    await loadReviewQueue();
  } catch (e) {
    showToast(e.response?.data?.detail || "批量通过失败", "error");
  } finally {
    batchActing.value = false;
  }
}

/* ─── 驳回对话框 ─── */
const rejectTarget = ref(null);
const batchRejecting = ref(false);
const rejectComment = ref("");
const rejecting = ref(false);
const rejectError = ref("");

function openReject(entry) {
  batchRejecting.value = false;
  rejectTarget.value = entry;
  rejectComment.value = "";
  rejectError.value = "";
}

function openBatchReject() {
  if (!selectedReviewIds.value.size) return;
  rejectTarget.value = null;
  batchRejecting.value = true;
  rejectComment.value = "";
  rejectError.value = "";
}

function closeReject() {
  rejectTarget.value = null;
  batchRejecting.value = false;
  rejectError.value = "";
}

async function confirmReject() {
  const comment = rejectComment.value.trim();
  if (!comment) return;
  rejectError.value = "";
  rejecting.value = true;
  try {
    if (batchRejecting.value) {
      const decisions = [...selectedReviewIds.value].map((sid) => ({ submission_id: sid, comment }));
      const res = await batchReject(decisions);
      const d = res.data || {};
      const s = d.summary || d;
      showToast(`驳回 ${s.rejected ?? 0} · 异常 ${s.error ?? 0}`);
      closeReject();
      await loadReviewQueue();
    } else if (rejectTarget.value) {
      await rejectSubmission(rejectTarget.value.submission_id, comment);
      showToast(`提交 #${rejectTarget.value.submission_id} 已驳回，条目进入返工箱`);
      removeReviewItem(rejectTarget.value.submission_id);
      closeReject();
    }
  } catch (e) {
    rejectError.value = e.response?.data?.detail || "驳回失败";
  } finally {
    rejecting.value = false;
  }
}

/* ───────── 看板 ───────── */
const COVERAGE_TABLES = [
  { key: "lit", label: "文献元数据" },
  { key: "case", label: "病案元数据" },
  { key: "guideline", label: "指南元数据" },
];
const boardLoading = ref(false);
const stats = ref({ pools: [], coverage: {}, users: [] });

function coverageOf(key) {
  const c = stats.value.coverage?.[key];
  return { annotated: c?.annotated ?? 0, total: c?.total ?? 0 };
}

function coveragePct(key) {
  const { annotated, total } = coverageOf(key);
  if (!total) return 0;
  return Math.min(100, Math.round((annotated / total) * 100));
}

function poolProgressPct(pool) {
  if (!pool.total_items) return 0;
  return Math.min(100, Math.round((pool.remaining_items / pool.total_items) * 100));
}

function formatRate(rate) {
  return `${Math.round((rate ?? 0) * 100)}%`;
}

function rateLevel(rate) {
  const r = rate ?? 0;
  if (r > 0.3) return "high";
  if (r > 0.1) return "mid";
  return "low";
}

async function loadBoard() {
  boardLoading.value = true;
  try {
    const res = await dashboardStats();
    stats.value = {
      pools: Array.isArray(res.data?.pools) ? res.data.pools : [],
      coverage: res.data?.coverage || {},
      users: Array.isArray(res.data?.users) ? res.data.users : [],
    };
  } catch (e) {
    showToast(e.response?.data?.detail || "加载看板失败", "error");
  } finally {
    boardLoading.value = false;
  }
}

/* ───────── 导出 ───────── */
const exportFilter = ref({ user_id: null, pool_id: null, date_from: "", date_to: "" });
const exporting = ref(false);
const exportError = ref("");

async function loadExportOptions() {
  try {
    const res = await fetchUsers();
    annotators.value = (res.data.users || []).filter((u) => u.role === "annotator");
  } catch (e) {
    annotators.value = [];
  }
  if (pools.value.length === 0) await loadPools();
}

function handleExportCsv() {
  exportError.value = "";
  exporting.value = true;
  const f = exportFilter.value;
  const params = {};
  if (f.user_id != null) params.user_id = f.user_id;
  if (f.pool_id != null) params.pool_id = f.pool_id;
  if (f.date_from) params.date_from = f.date_from;
  if (f.date_to) params.date_to = f.date_to;
  exportCsv(params)
    .then((res) => {
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "workload.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showToast("导出成功：workload.csv 已开始下载");
    })
    .catch(() => {
      // blob 响应的错误体无法读 detail，统一降级文案
      exportError.value = "导出失败，请稍后重试";
    })
    .finally(() => {
      exporting.value = false;
    });
}

/* ───────── 回滚日志 ───────── */
const LOG_ACTIONS = [
  "approve",
  "reject",
  "expire",
  "rollback",
  "save_direct",
  "claim",
  "assign",
  "draft",
  "no_change",
  "submit",
];
const ACTION_META = {
  approve: { label: "通过", cls: "badge-action-approve" },
  reject: { label: "驳回", cls: "badge-action-reject" },
  expire: { label: "过期", cls: "badge-action-expire" },
  rollback: { label: "回滚", cls: "badge-action-rollback" },
  save_direct: { label: "直改", cls: "badge-action-neutral" },
  claim: { label: "领取", cls: "badge-action-neutral" },
  assign: { label: "代派", cls: "badge-action-neutral" },
  draft: { label: "草稿", cls: "badge-action-neutral" },
  no_change: { label: "无变更", cls: "badge-action-neutral" },
  submit: { label: "提交", cls: "badge-action-submit" },
};

function actionMeta(action) {
  return ACTION_META[action] || { label: action, cls: "badge-action-neutral" };
}

const LOG_PAGE_SIZE = 20;
const logFilters = ref({ table_name: "", action: "", record_id: "" });
const logPage = ref(1);
const logTotal = ref(0);
const logs = ref([]);
const logsLoading = ref(false);
const rollingBackId = ref(null);

const logPageCount = computed(() => Math.max(1, Math.ceil(logTotal.value / LOG_PAGE_SIZE)));

function logParams() {
  const f = logFilters.value;
  const params = { page: logPage.value, page_size: LOG_PAGE_SIZE };
  if (f.table_name) params.table_name = f.table_name;
  if (f.action) params.action = f.action;
  if (f.record_id !== "" && f.record_id !== null && Number.isFinite(Number(f.record_id))) {
    params.record_id = Number(f.record_id);
  }
  return params;
}

async function loadLogs() {
  logsLoading.value = true;
  try {
    const res = await queryLogs(logParams());
    logs.value = Array.isArray(res.data?.items) ? res.data.items : [];
    logTotal.value = res.data?.total ?? 0;
  } catch (e) {
    logs.value = [];
    showToast(e.response?.data?.detail || "加载日志失败", "error");
  } finally {
    logsLoading.value = false;
  }
}

function resetAndLoadLogs() {
  logPage.value = 1;
  loadLogs();
}

function goLogPage(page) {
  if (page < 1 || page > logPageCount.value) return;
  logPage.value = page;
  loadLogs();
}

function hasOldFields(log) {
  return !!log.old_fields && typeof log.old_fields === "object" && Object.keys(log.old_fields).length > 0;
}

// 变更摘要单值：数组顿号连接，对象 JSON 化，空值显示 "-"
function compactValue(v) {
  if (v === null || v === undefined || v === "") return "-";
  if (Array.isArray(v)) return v.length ? v.join("、") : "-";
  if (typeof v === "object") return JSON.stringify(v);
  return `"${String(v)}"`;
}

function changeSummary(log) {
  const oldF = log.old_fields || {};
  const newF = log.new_fields || {};
  const keys = [...new Set([...Object.keys(oldF), ...Object.keys(newF)])];
  if (keys.length === 0) return "-";
  return keys.map((k) => `${k}: ${compactValue(oldF[k])} → ${compactValue(newF[k])}`).join("; ");
}

async function handleRollback(log) {
  const restoreKeys = Object.keys(log.old_fields || {});
  const detail = restoreKeys
    .map((k) => `${k}: ${compactValue(log.new_fields?.[k])} → ${compactValue(log.old_fields[k])}`)
    .join("; ");
  if (
    !confirm(
      `确定回滚日志 #${log.id} 吗？\n将把记录 #${log.record_id}（${tableLabel(log.table_name)}）恢复为：\n${detail}`
    )
  ) {
    return;
  }
  rollingBackId.value = log.id;
  try {
    await rollbackLog(log.id);
    showToast(`日志 #${log.id} 已回滚，记录 #${log.record_id} 字段已恢复`);
    await loadLogs(); // 重取当前页：列表顶部会出现新的 rollback 审计行
  } catch (e) {
    showToast(e.response?.data?.detail || "回滚失败", "error");
  } finally {
    rollingBackId.value = null;
  }
}

onMounted(loadPools);

// 进入复核/看板/导出/回滚页签时按需拉取数据
watch(activeTab, (tab) => {
  if (tab === "review") loadReviewQueue();
  else if (tab === "board") loadBoard();
  else if (tab === "export") loadExportOptions();
  else if (tab === "rollback") resetAndLoadLogs();
});
</script>

<style scoped>
.admin-page { width: 100%; padding: 24px 32px; height: 100vh; overflow-y: scroll; }

.admin-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.admin-header h1 { font-size: 22px; font-weight: 600; color: #1a1a2e; margin: 0; }

.mgmt-tabs { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #e0e0e0; }
.mgmt-tab { padding: 9px 18px; border: none; background: transparent; font-size: 13px; color: #666; cursor: pointer; border-radius: 6px 6px 0 0; position: relative; top: 2px; border-bottom: 2px solid transparent; }
.mgmt-tab:hover { color: #00796b; background: #f0f7f6; }
.mgmt-tab-active { color: #00796b; font-weight: 600; border-bottom-color: #00796b; background: transparent; }

.loading { text-align: center; padding: 48px 0; color: #999; font-size: 14px; }

/* ── 任务池子页签 ── */
.pool-subtabs { display: flex; gap: 8px; margin-bottom: 14px; }
.pool-subtab { padding: 6px 18px; border: 1px solid #d0d0d0; border-radius: 16px; background: #fff; font-size: 13px; color: #666; cursor: pointer; }
.pool-subtab:hover { border-color: #00796b; color: #00796b; }
.pool-subtab-active { background: #00796b; border-color: #00796b; color: #fff; font-weight: 500; }
.pool-subtab-active:hover { color: #fff; }

/* ── 建池向导 ── */
.wizard-card { border: 1px solid #e0e0e0; border-radius: 10px; margin-bottom: 20px; background: #fff; overflow: hidden; }
.wizard-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; cursor: pointer; user-select: none; }
.wizard-header:hover { background: #f0f7f6; }
.wizard-header h2 { font-size: 15px; font-weight: 600; color: #1a1a2e; margin: 0; }
.btn-wizard-toggle { color: #00796b; border-color: #b2dfdb; }
.btn-wizard-toggle:hover { background: #e0f2f1; }
.wizard-body { padding: 4px 16px 16px; border-top: 1px solid #eee; }

.wizard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px 16px; margin-top: 12px; }
.form-field { margin-bottom: 0; }
.form-field label { display: block; font-size: 12px; font-weight: 500; color: #666; margin-bottom: 4px; }
.form-field input, .form-field select { width: 100%; padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; box-sizing: border-box; background: #fff; }
.form-field input:focus, .form-field select:focus { border-color: #00796b; }

.year-range { display: flex; align-items: center; gap: 6px; }
.year-range input { min-width: 0; }
.year-sep { color: #999; }

.wizard-actions { display: flex; gap: 10px; margin-top: 14px; }
.btn-create { padding: 8px 20px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; }
.btn-create:hover { background: #00695c; }
.btn-create:disabled { opacity: 0.5; cursor: default; }
.btn-confirm { background: #ff8f00; }
.btn-confirm:hover { background: #f57c00; }
.btn-confirm:disabled { opacity: 0.5; cursor: default; }
.btn-select-all { background: #5e35b1; }
.btn-select-all:hover { background: #4527a0; }
.btn-select-all-active { background: #c62828; }
.btn-select-all-active:hover { background: #b71c1c; }

.preview-result { margin: 12px 0 0; padding: 8px 12px; border-radius: 6px; background: #e0f2f1; color: #00695c; font-size: 13px; }
.form-error { color: #c62828; font-size: 12px; margin: 10px 0 0; }

/* ── 占位页签 ── */
.placeholder-card { border: 1px dashed #d0d0d0; border-radius: 10px; padding: 64px 0; text-align: center; color: #999; font-size: 14px; background: #fafafa; }

/* ── 池列表 ── */
.table-wrap { overflow-x: auto; }
.pool-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pool-table th { text-align: left; padding: 10px 12px; background: #f5f5f5; color: #666; font-weight: 500; border-bottom: 2px solid #e0e0e0; white-space: nowrap; }
.pool-table td { padding: 10px 12px; border-bottom: 1px solid #eee; color: #333; vertical-align: middle; }
.pool-table tr:hover { background: #fafafa; }
.cell-priority { font-weight: 600; color: #00796b; }
.cell-time { color: #888; font-size: 12px; white-space: nowrap; }
.cell-actions { white-space: nowrap; }
.empty-row { text-align: center; color: #999; padding: 40px 12px !important; }

.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.badge-active { background: #e8f5e9; color: #2e7d32; }
.badge-paused { background: #fff8e1; color: #f57f17; }
.badge-closed { background: #f5f5f5; color: #666; }

.progress-cell { display: flex; align-items: center; gap: 8px; min-width: 140px; }
.progress-track { flex: 1; height: 8px; border-radius: 4px; background: #eeeeee; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 4px; background: #00796b; transition: width 0.3s ease; }
.progress-text { font-size: 12px; color: #666; white-space: nowrap; }

.btn-sm { padding: 3px 10px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 12px; cursor: pointer; background: #fff; }
.btn-assign { color: #00796b; border-color: #b2dfdb; }
.btn-assign:hover { background: #e0f2f1; }
.btn-toggle { color: #e65100; border-color: #ffcc80; }
.btn-toggle:hover { background: #fff3e0; }
.btn-delete { color: #c62828; border-color: #ef9a9a; }
.btn-delete:hover { background: #ffebee; }
.btn-priority { color: #5e35b1; border-color: #d1c4e9; }
.btn-priority:hover { background: #ede7f6; }

/* ── 指派对话框 ── */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; border-radius: 12px; width: 480px; max-height: 80vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid #e8e8e8; }
.modal-header h2 { font-size: 15px; font-weight: 600; margin: 0; }
.modal-close { width: 28px; height: 28px; border: none; background: transparent; font-size: 20px; color: #999; cursor: pointer; border-radius: 4px; }
.modal-close:hover { background: #f0f0f0; color: #333; }
.modal-body { padding: 20px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid #e8e8e8; }

.annotator-hint { font-size: 12px; color: #888; margin: 0 0 10px; }
.empty-hint { text-align: center; color: #999; font-size: 13px; padding: 24px 0; }
.annotator-row { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.annotator-row:hover { background: #f0f7f6; }
.annotator-row input[type="checkbox"] { accent-color: #00796b; }
.annotator-name { font-weight: 500; color: #333; }
.annotator-email { color: #999; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.assign-results { margin-top: 14px; padding-top: 12px; border-top: 1px dashed #e0e0e0; }
.assign-results h3 { font-size: 13px; font-weight: 600; color: #666; margin: 0 0 8px; }
.assign-results p { margin: 4px 0; font-size: 13px; }
.result-ok { color: #2e7d32; }
.result-fail { color: #c62828; }

.btn-cancel { padding: 8px 20px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; font-size: 13px; cursor: pointer; color: #666; }
.btn-cancel:hover { background: #f0f0f0; }
.btn-save { padding: 8px 20px; border: none; border-radius: 6px; background: #00796b; color: #fff; font-size: 13px; cursor: pointer; }
.btn-save:hover { background: #00695c; }
.btn-save:disabled { opacity: 0.6; cursor: default; }

/* ── 复核队列（平铺分页） ── */
.review-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.review-select-all { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #333; cursor: pointer; user-select: none; }
.review-count { margin-left: auto; font-size: 12px; color: #666; }
.review-count strong { color: #00796b; }
.review-pager { display: flex; align-items: center; gap: 10px; }
.review-pager .btn-sm:disabled { opacity: 0.5; cursor: default; }

.review-table { font-size: 13px; }
.rev-col-check { width: 36px; text-align: center; }
.rev-col-id { width: 80px; white-space: nowrap; }
.rev-summary { font-size: 12px; }

.review-row-selected td { background: #f0f7f6 !important; }
.review-row-core-missing td { background: #fff8f8 !important; }
.review-row-core-missing .btn-review-approve { opacity: 0.4; cursor: not-allowed; }

.core-missing-badge { display: inline-block; margin-left: 6px; padding: 1px 6px; border-radius: 4px; background: #ffebee; color: #c62828; font-size: 11px; }
.btn-review-approve { color: #00796b; border-color: #b2dfdb; }
.btn-review-approve:hover:not(:disabled) { background: #e0f2f1; }
.btn-review-reject { color: #c62828; border-color: #ef9a9a; }
.btn-review-reject:hover:not(:disabled) { background: #ffebee; }
.btn-review-approve:disabled, .btn-review-reject:disabled { opacity: 0.5; cursor: default; }

.badge-no-diff { background: #f5f5f5; color: #999; }
.badge-has-diff { background: #e0f2f1; color: #00695c; }
.badge-pending { background: #fff8e1; color: #f57f17; }
.btn-review-expand { color: #00796b; border-color: #b2dfdb; }
.btn-review-expand:hover { background: #e0f2f1; }

.review-expand-row td { padding: 0 !important; border-bottom: 1px solid #e0e0e0; }
.review-expand-cell { padding: 12px 16px !important; background: #fafafa; }

.diff-legend { padding: 0 0 6px; font-size: 12px; color: #b06a00; }
.diff-legend-mark { color: #b06a00; }
.diff-grid { display: grid; grid-template-columns: 1fr 1fr; }
.diff-col { min-width: 0; padding: 8px 12px 10px; }
.diff-col-current { border-right: 1px dashed #e0e0e0; }
.diff-col-proposed { background: #f0f7f6; }
.diff-col-title { margin-bottom: 6px; font-size: 11px; font-weight: 600; letter-spacing: 2px; color: #999; }
.diff-col-proposed .diff-col-title { color: #00796b; }
.diff-row { display: flex; align-items: baseline; gap: 10px; padding: 3px 0; border-bottom: 1px dotted #f0f0f0; font-size: 12px; }
.diff-row:last-child { border-bottom: none; }
.diff-key { flex-shrink: 0; width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #999; }
.diff-val { min-width: 0; word-break: break-all; color: #333; }
.diff-col-proposed .diff-val { color: #00695c; font-weight: 500; }
.diff-changed { background: rgba(199, 124, 0, 0.12); border-left: 3px solid #b06a00; }

.form-field textarea { width: 100%; padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; outline: none; box-sizing: border-box; resize: vertical; font-family: inherit; line-height: 1.6; }
.form-field textarea:focus { border-color: #00796b; }
.btn-reject-confirm { background: #c62828; }
.btn-reject-confirm:hover:not(:disabled) { background: #b71c1c; }

/* ── 看板 ── */
.coverage-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 4px; }
.coverage-card { border: 1px solid #e0e0e0; border-radius: 10px; background: #fff; padding: 16px; }
.coverage-card h3 { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: #666; }
.coverage-num { margin: 0 0 10px; font-size: 15px; font-weight: 600; color: #00796b; }
.coverage-track { height: 10px; }
.board-section-title { margin: 22px 0 10px; font-size: 15px; font-weight: 600; color: #1a1a2e; }

.rate-high { color: #c62828; font-weight: 600; }
.rate-mid { color: #f57f17; font-weight: 600; }
.rate-low { color: #2e7d32; }

/* ── 导出 ── */
.export-body { padding-top: 12px; }

/* ── 回滚日志 ── */
.log-filters { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.filter-select, .filter-input { padding: 7px 10px; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 13px; background: #fff; outline: none; }
.filter-select:focus, .filter-input:focus { border-color: #00796b; }
.filter-input { width: 130px; }
.logs-table .cell-summary { max-width: 420px; word-break: break-all; color: #555; font-size: 12px; }

.badge-action-approve { background: #e8f5e9; color: #2e7d32; }
.badge-action-reject { background: #ffebee; color: #c62828; }
.badge-action-expire { background: #fff8e1; color: #f57f17; }
.badge-action-rollback { background: #ede7f6; color: #5e35b1; }
.badge-action-submit { background: #e0f2f1; color: #00695c; }
.badge-action-neutral { background: #f5f5f5; color: #666; }

.pager { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
.pager-info { font-size: 12px; color: #888; }
.pager .btn-sm:disabled { opacity: 0.5; cursor: default; }

/* ── toast ── */
.toast { position: fixed; top: 24px; right: 24px; z-index: 2000; padding: 12px 18px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,0.18); max-width: 420px; }
.toast-success { background: #00796b; color: #fff; }
.toast-error { background: #c62828; color: #fff; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(-8px); }

/* ── 建池向导·明细表 (wiz-*) ── */
.wiz-toggle-field { display: flex; align-items: flex-end; }
.wiz-toggle-label { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 13px; color: #333; padding-bottom: 8px; }
.wiz-checkbox { accent-color: #00796b; width: 15px; height: 15px; cursor: pointer; }

.wiz-preview { margin-top: 14px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; }
.wiz-preview-toolbar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; background: #f5f5f5; border-bottom: 1px solid #e0e0e0; }
.wiz-selected-count { margin-left: auto; font-size: 12px; color: #666; }
.wiz-selected-count strong { color: #00796b; }

.wiz-table-wrap { overflow-x: auto; max-height: 420px; overflow-y: auto; }
.wiz-preview-table { font-size: 12px; }
.wiz-preview-table th { position: sticky; top: 0; z-index: 1; background: #f5f5f5; }
.wiz-col-check { width: 36px; text-align: center; }
.wiz-col-id { width: 60px; white-space: nowrap; }
.wiz-col-title { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wiz-col-status { width: 80px; white-space: nowrap; }
.wiz-col-year { width: 60px; white-space: nowrap; }
.wiz-col-pool { width: 100px; white-space: nowrap; }

.wiz-row-disabled { background: #fafafa; color: #aaa; }
.wiz-row-disabled td { color: #aaa; }
.wiz-row-disabled .badge { opacity: 0.6; }

.badge-eligible { background: #e8f5e9; color: #2e7d32; }
.badge-blocked { background: #f5f5f5; color: #999; }
.badge-crawl-success { background: #e8f5e9; color: #2e7d32; }
.badge-crawl-partial { background: #fff8e1; color: #f57f17; }
.badge-crawl-failed { background: #ffebee; color: #c62828; }
.badge-crawl-default { background: #f5f5f5; color: #666; }

.wiz-pager { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 8px 12px; border-top: 1px solid #e0e0e0; background: #fafafa; }
.wiz-pager .btn-sm:disabled { opacity: 0.5; cursor: default; }
</style>
