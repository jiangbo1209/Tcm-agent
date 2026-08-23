"""APP_ENV / FILE_TOKEN_SECRET 配置面与生产环境 fail-fast 启动守卫。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import DEFAULT_JWT_SECRET_KEY, AuthSettings, get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolate_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- 配置面（todo 1：alias 必须绕开 JWT_ 前缀）---


def test_auth_defaults_are_development_and_empty_file_secret():
    auth = AuthSettings()
    assert auth.app_env == "development"
    assert auth.file_token_secret == ""
    assert auth.secret_key == DEFAULT_JWT_SECRET_KEY


def test_env_aliases_bypass_jwt_prefix(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FILE_TOKEN_SECRET", "s3cr3t")
    auth = AuthSettings()
    assert auth.app_env == "production"
    assert auth.file_token_secret == "s3cr3t"


def test_non_production_app_env_stays_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    auth = AuthSettings()
    assert auth.app_env == "prod"
    assert auth.app_env != "production"


# --- 生产 fail-fast 守卫（todo 3）---
# import main 在模块顶层即执行 ensure_* 列迁移并连接 PostgreSQL；本机无可用 PG，
# 故经子进程以 POSTGRES_HOST=127.0.0.1（立即拒连）驱动真实启动路径。
# 守卫位于 ensure_* 之前：生产态拒绝先于任何 DB 访问，与 PG 是否可达无关。


def _run_import_main(extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        **extra_env,
    }
    return subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_production_with_default_jwt_secret_refuses_to_start():
    proc = _run_import_main({"APP_ENV": "production"})
    assert proc.returncode != 0
    assert "RuntimeError" in proc.stderr
    assert "JWT_SECRET_KEY" in proc.stderr


def test_production_with_missing_file_token_secret_refuses_to_start():
    proc = _run_import_main({"APP_ENV": "production", "JWT_SECRET_KEY": "real-prod-key"})
    assert proc.returncode != 0
    assert "RuntimeError" in proc.stderr
    assert "FILE_TOKEN_SECRET" in proc.stderr


def test_production_with_both_secrets_passes_guard_then_hits_db():
    proc = _run_import_main(
        {
            "APP_ENV": "production",
            "JWT_SECRET_KEY": "real-prod-key",
            "FILE_TOKEN_SECRET": "real-file-secret",
        }
    )
    # 本机无 PG：守卫放行后进程死于数据库连接，而非密钥守卫。
    assert "RuntimeError" not in proc.stderr
    assert "OperationalError" in proc.stderr


def test_development_defaults_do_not_raise():
    proc = _run_import_main({})
    assert "RuntimeError" not in proc.stderr
