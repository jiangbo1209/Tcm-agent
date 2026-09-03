"""File-stream token security: roundtrip, tamper rejection, key rotation isolation."""

import hashlib

import pytest

from app.config import DEFAULT_JWT_SECRET_KEY, get_auth_config, get_settings
from app.storage.file_token import (
    _resolve_secret_key,
    generate_file_token,
    validate_file_token,
)


@pytest.fixture(autouse=True)
def _isolate_key_caches():
    """派生函数与 get_settings 均为 lru_cache：前后清空，保证 patch 生效且不跨用例泄漏。"""
    get_settings.cache_clear()
    _resolve_secret_key.cache_clear()
    yield
    get_settings.cache_clear()
    _resolve_secret_key.cache_clear()


def _make_token() -> str:
    return generate_file_token("literature/u1/a.pdf", "a.pdf", "inline")


def _rotate_secret(monkeypatch: pytest.MonkeyPatch, secret: str) -> None:
    """Settings.auth 是类级默认值，pydantic 每次实例化都会拷贝一份——
    必须先清两级 lru_cache 再改「当前缓存实例」的属性，顺序颠倒则 patch 随缓存重建丢失。"""
    get_settings.cache_clear()
    _resolve_secret_key.cache_clear()
    monkeypatch.setattr(get_auth_config(), "file_token_secret", secret)


# --- 现行为钉扎（基线 characterization，改动前后均须通过）---


def test_roundtrip_preserves_payload():
    token = _make_token()
    storage_path, file_name, disposition = validate_file_token(token)
    assert (storage_path, file_name, disposition) == (
        "literature/u1/a.pdf",
        "a.pdf",
        "inline",
    )


def test_tampered_payload_byte_rejected():
    token = _make_token()
    encoded, sig = token.split(".", 1)
    tampered_char = "X" if encoded[0] != "X" else "Y"
    with pytest.raises(ValueError):
        validate_file_token(f"{tampered_char}{encoded[1:]}.{sig}")


# --- 密钥派生契约（todo 2）---


def test_default_derivation_uses_jwt_secret_with_domain_separator():
    expected = hashlib.sha256(f"{DEFAULT_JWT_SECRET_KEY}|file-stream".encode()).digest()
    assert _resolve_secret_key() == expected


def test_explicit_file_token_secret_overrides_fallback(monkeypatch):
    _rotate_secret(monkeypatch, "rotated-secret")
    assert _resolve_secret_key() == hashlib.sha256(b"rotated-secret").digest()


# --- 篡改拒识与密钥隔离（todo 2）---


def test_tampered_payload_rejected_under_rotated_secret(monkeypatch):
    _rotate_secret(monkeypatch, "rotated-secret")
    token = _make_token()
    encoded, sig = token.split(".", 1)
    tampered_char = "X" if encoded[0] != "X" else "Y"
    with pytest.raises(ValueError):
        validate_file_token(f"{tampered_char}{encoded[1:]}.{sig}")


def test_old_token_rejected_after_file_token_secret_rotation(monkeypatch):
    old_token = _make_token()
    _rotate_secret(monkeypatch, "rotated-secret")
    with pytest.raises(ValueError):
        validate_file_token(old_token)
    storage_path, _, _ = validate_file_token(_make_token())
    assert storage_path == "literature/u1/a.pdf"
