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
	@echo "TCM-Agent 服务管理"
	@echo "  make all-up       启动数据库 + 前后端"
	@echo "  make start        启动前后端（后台）"
	@echo "  make stop         停止前后端"
	@echo "  make stop-all     停止前后端 + 数据库"
	@echo "  make db-up        启动数据库 + MinIO"
	@echo "  make db-down      停止数据库 + MinIO"
	@echo "  make db-init      初始化 PostgreSQL 表结构"
	@echo "  make graph-build  生成图谱底表 nodes/edges"
	@echo "  make clean        清理缓存和日志"

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

db-up:
	docker-compose up -d postgresql minio
	@echo "PostgreSQL: localhost:5432  MinIO 控制台: http://localhost:9001"

db-down:
	docker-compose down postgresql minio

db-init: check-env
	$(PYTHON) -m data_process.db_init

graph-build: check-env
	$(PYTHON) -m data_process.graph_builder

all-up: db-up start

stop-all: stop db-down

clean:
	@find $(BACKEND_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find $(BACKEND_DIR) -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf $(LOGS)
	@echo "清理完成"