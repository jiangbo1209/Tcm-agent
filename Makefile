.PHONY: help start stop clean db-up db-down db-init graph-build all-up stop-all check-env
.DEFAULT_GOAL := help

CONDA_ENV     := Tcm-agent
PYTHON        := conda run -n $(CONDA_ENV) python
BACKEND_DIR   := UI/backend
FRONTEND_DIR  := UI/frontend
BACKEND_PORT  := 8011
FRONTEND_PORT := 5500
LOGS          := /tmp/tcm

help:
	@echo "TCM-Agent 完整服务启动脚本"
	@echo ""
	@echo "=== 前后端服务 ==="
	@echo "  make start              - 启动前后端服务"
	@echo "  make start-backend      - 仅启动后端服务"
	@echo "  make start-frontend     - 仅启动前端服务"
	@echo "  make dev                - 开发模式启动前后端"
	@echo ""
	@echo "=== 数据库 & 存储 (Docker Compose) ==="
	@echo "  make db-up              - 启动数据库"
	@echo "  make db-init            - 初始化 PostgreSQL 表结构"
	@echo "  make graph-build        - 生成 nodes/edges 图谱底表"
	@echo "  make db-down            - 停止数据库"
	@echo "  make db-logs            - 查看数据库日志"
	@echo "  make db-shell           - 进入数据库容器 psql shell"
	@echo ""
	@echo "=== 系统控制 ==="
	@echo "  make stop               - 停止所有前后端服务"
	@echo "  make stop-all           - 停止所有服务（含数据库）"
	@echo "  make logs               - 查看前后端日志"
	@echo "  make status             - 查看服务状态"
	@echo "  make clean              - 清理缓存和临时文件"
	@echo ""
	@echo "=== 快速启动 (推荐) ==="
	@echo "  make all-up             - 一键启动全部服务（数据库 + 前后端）"

check-env:
	@$(PYTHON) --version > /dev/null 2>&1 || (echo "conda 环境 $(CONDA_ENV) 不存在" && exit 1)

start: check-env
	@mkdir -p $(LOGS)
	@cd $(BACKEND_DIR)  && nohup $(PYTHON) -m uvicorn main:app --host 0.0.0.0 --port $(BACKEND_PORT)  > $(LOGS)/backend.log  2>&1 & echo $$! > $(LOGS)/backend.pid
	@cd $(FRONTEND_DIR) && nohup npx vite --host 0.0.0.0 --port $(FRONTEND_PORT)                  > $(LOGS)/frontend.log 2>&1 & echo $$! > $(LOGS)/frontend.pid
	@echo "前端:     http://localhost:$(FRONTEND_PORT)"
	@echo "后端:     http://localhost:$(BACKEND_PORT)"
	@echo "API 文档: http://localhost:$(BACKEND_PORT)/docs"

stop:
	@-fuser -k $(BACKEND_PORT)/tcp 2>/dev/null
	@-fuser -k $(FRONTEND_PORT)/tcp 2>/dev/null
	@rm -f $(LOGS)/*.pid
	@echo "服务已停止"

# ============================================================
# 数据库 & 存储服务 (Docker Compose)
# ============================================================

db-up:
	@echo "启动数据库 (PostgreSQL + pgvector)..."
	@docker-compose up -d postgresql
	@sleep 3
	@echo "✓ 数据库服务已启动"
	@echo ""
	@echo "数据库信息:"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  对象存储: (S3_ENDPOINT: $${S3_ENDPOINT:-未设置})"
	@docker-compose logs -n 20 postgresql

# 初始化 PostgreSQL 表结构
db-init: check-env
	@echo "初始化 PostgreSQL 表结构..."
	@$(PYTHON) -m data_process.db_init
	@echo "✓ 数据库表结构初始化完成"

# 生成 nodes/edges 图谱底表
graph-build: check-env
	@echo "生成图谱底表 nodes/edges..."
	@$(PYTHON) -m data_process.graph_builder
	@echo "✓ 图谱底表生成完成"

# 停止数据库
db-down:
	@echo "停止数据库..."
	@docker-compose down postgresql
	@echo "✓ 数据库服务已停止"

# 查看数据库日志
db-logs:
	@docker-compose logs -f postgresql

# 进入数据库 psql shell
db-shell:
	@echo "连接到 PostgreSQL..."
	@docker-compose exec postgresql psql -U postgres -d papers_records

# 查看所有 Docker Compose 服务状态
docker-status:
	@echo "Docker Compose 服务状态:"
	@docker-compose ps

all-up: db-up start
	@echo ""
	@echo "========================================="
	@echo "✓ 全部服务已启动"
	@echo "========================================="
	@echo "前端:       http://localhost:$(FRONTEND_PORT)"
	@echo "后端 API:   http://localhost:$(BACKEND_PORT)"
	@echo "API 文档:   http://localhost:$(BACKEND_PORT)/docs"
	@echo "对象存储:   COS ($S3_ENDPOINT)"
	@echo "PostgreSQL: localhost:5432"
	@echo ""
	@echo "停止所有: make stop-all"
	@echo "查看状态: make status"
	@echo "========================================="

stop-all: stop db-down

clean:
	@find $(BACKEND_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find $(BACKEND_DIR) -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf $(LOGS)
	@echo "清理完成"
