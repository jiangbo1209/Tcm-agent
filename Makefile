.PHONY: help backend frontend server all dev stop logs database db-up db-down db-logs db-shell

# 环境变量
CONDA_ENV := Tcm-agent
BACKEND_DIR := UI/backend
FRONTEND_DIR := UI/frontend
BACKEND_PORT := 8011
FRONTEND_PORT := 5500

# 帮助信息
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
	@echo "  make db-up              - 启动数据库 + MinIO"
	@echo "  make db-down            - 停止数据库 + MinIO"
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

# 检查conda环境
check-env:
	@echo "检查 Conda 环境: $(CONDA_ENV)"
	@conda run -n $(CONDA_ENV) python --version || (echo "环境 $(CONDA_ENV) 不存在!" && exit 1)

# 启动后端服务
start-backend: check-env
	@echo "启动后端服务 (端口: $(BACKEND_PORT))..."
	@cd $(BACKEND_DIR) && conda run -n $(CONDA_ENV) uvicorn main:app --host 0.0.0.0 --port $(BACKEND_PORT)

# 启动前端服务
start-frontend:
	@echo "启动前端服务 (端口: $(FRONTEND_PORT))..."
	@cd $(FRONTEND_DIR) && python3 -m http.server $(FRONTEND_PORT)

# 后台启动后端（用于 make all）
start-backend-bg: check-env
	@echo "启动后端服务 (后台运行，端口: $(BACKEND_PORT))..."
	@cd $(BACKEND_DIR) && conda run -n $(CONDA_ENV) uvicorn main:app --host 0.0.0.0 --port $(BACKEND_PORT) > /tmp/tcm-backend.log 2>&1 &
	@echo "$$!" > /tmp/tcm-backend.pid
	@sleep 2
	@echo "后端服务已启动 (PID: `cat /tmp/tcm-backend.pid`)"

# 后台启动前端（用于 make all）
start-frontend-bg:
	@echo "启动前端服务 (后台运行，端口: $(FRONTEND_PORT))..."
	@cd $(FRONTEND_DIR) && python3 -m http.server $(FRONTEND_PORT) > /tmp/tcm-frontend.log 2>&1 &
	@echo "$$!" > /tmp/tcm-frontend.pid
	@sleep 1
	@echo "前端服务已启动 (PID: `cat /tmp/tcm-frontend.pid`)"

# 启动所有服务（前后端）
start: start-backend-bg start-frontend-bg
	@echo ""
	@echo "========================================="
	@echo "✓ 所有服务已启动"
	@echo "========================================="
	@echo "前端访问地址: http://localhost:$(FRONTEND_PORT)"
	@echo "后端API地址: http://localhost:$(BACKEND_PORT)"
	@echo "API文档地址: http://localhost:$(BACKEND_PORT)/docs"
	@echo ""
	@echo "查看日志: make logs"
	@echo "停止服务: make stop"
	@echo "========================================="

# 开发模式启动（前后端在前台运行，便于查看日志）
dev:
	@echo "开发模式启动前后端服务..."
	@echo "按 Ctrl+C 停止"
	@if pgrep -f "http.server $(FRONTEND_PORT)" > /dev/null 2>&1; then \
		pkill -f "http.server $(FRONTEND_PORT)"; \
		sleep 1; \
	fi
	@if [ -f /tmp/tcm-backend.pid ]; then \
		kill `cat /tmp/tcm-backend.pid` 2>/dev/null || true; \
		rm -f /tmp/tcm-backend.pid; \
	fi
	@$(MAKE) start

# 停止所有服务
stop:
	@echo "停止所有服务..."
	@if [ -f /tmp/tcm-backend.pid ]; then \
		kill `cat /tmp/tcm-backend.pid` 2>/dev/null && echo "✓ 后端服务已停止" || true; \
		rm -f /tmp/tcm-backend.pid; \
	else \
		pkill -f "uvicorn main:app" 2>/dev/null && echo "✓ 后端服务已停止" || true; \
	fi
	@if [ -f /tmp/tcm-frontend.pid ]; then \
		kill `cat /tmp/tcm-frontend.pid` 2>/dev/null && echo "✓ 前端服务已停止" || true; \
		rm -f /tmp/tcm-frontend.pid; \
	else \
		pkill -f "http.server $(FRONTEND_PORT)" 2>/dev/null && echo "✓ 前端服务已停止" || true; \
	fi
	@echo "所有服务已停止"

# 查看日志
logs:
	@echo "后端日志:"
	@if [ -f /tmp/tcm-backend.log ]; then tail -f /tmp/tcm-backend.log; else echo "没有后端日志"; fi
	@echo ""
	@echo "前端日志:"
	@if [ -f /tmp/tcm-frontend.log ]; then tail -f /tmp/tcm-frontend.log; else echo "没有前端日志"; fi

# 清理缓存
clean:
	@echo "清理缓存和临时文件..."
	@find $(BACKEND_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find $(BACKEND_DIR) -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -f /tmp/tcm-backend.log /tmp/tcm-frontend.log /tmp/tcm-*.pid
	@echo "✓ 清理完成"

# 安装后端依赖
install-backend: check-env
	@echo "安装后端依赖..."
	@cd $(BACKEND_DIR) && conda run -n $(CONDA_ENV) pip install -r requirements.txt
	@echo "✓ 后端依赖安装完成"

# 显示状态
status:
	@echo "服务状态:"
	@if [ -f /tmp/tcm-backend.pid ] && kill -0 `cat /tmp/tcm-backend.pid` 2>/dev/null; then \
		echo "✓ 后端服务运行中 (PID: `cat /tmp/tcm-backend.pid`)"; \
	else \
		echo "✗ 后端服务未运行"; \
	fi
	@if [ -f /tmp/tcm-frontend.pid ] && kill -0 `cat /tmp/tcm-frontend.pid` 2>/dev/null; then \
		echo "✓ 前端服务运行中 (PID: `cat /tmp/tcm-frontend.pid`)"; \
	else \
		echo "✗ 前端服务未运行"; \
	fi

# ============================================================
# 数据库 & 存储服务 (Docker Compose)
# ============================================================

# 启动数据库 + MinIO
db-up:
	@echo "启动数据库 (PostgreSQL + pgvector) 和 MinIO..."
	@docker-compose up -d postgresql minio
	@sleep 3
	@echo "✓ 数据库服务已启动"
	@echo ""
	@echo "数据库信息:"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  MinIO S3:   localhost:9000"
	@echo "  MinIO Web:  http://localhost:9001"
	@docker-compose logs -n 20 postgresql minio

# 停止数据库 + MinIO
db-down:
	@echo "停止数据库和 MinIO..."
	@docker-compose down postgresql minio
	@echo "✓ 数据库服务已停止"

# 查看数据库日志
db-logs:
	@docker-compose logs -f postgresql

# 进入数据库 psql shell
db-shell:
	@echo "连接到 PostgreSQL..."
	@docker-compose exec postgresql psql -U postgres -d papers_records

# 查看 MinIO 日志
minio-logs:
	@docker-compose logs -f minio

# 查看所有 Docker Compose 服务状态
docker-status:
	@echo "Docker Compose 服务状态:"
	@docker-compose ps

# 一键启动全部服务（数据库 + 前后端）
all-up: db-up start
	@echo ""
	@echo "========================================="
	@echo "✓ 全部服务已启动"
	@echo "========================================="
	@echo "前端:       http://localhost:$(FRONTEND_PORT)"
	@echo "后端 API:   http://localhost:$(BACKEND_PORT)"
	@echo "API 文档:   http://localhost:$(BACKEND_PORT)/docs"
	@echo "MinIO 后台: http://localhost:9001"
	@echo "PostgreSQL: localhost:5432"
	@echo ""
	@echo "停止所有: make stop-all"
	@echo "查看状态: make status"
	@echo "========================================="

# 停止所有服务（含数据库）
stop-all: stop db-down
	@echo "✓ 所有服务已停止（包含数据库）"
