"""Pydantic settings for graph builder runtime configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class GraphBuilderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("POSTGRES_HOST"),
    )
    port: int = Field(
        default=5432,
        validation_alias=AliasChoices("POSTGRES_PORT"),
    )
    user: str = Field(
        default="postgres",
        validation_alias=AliasChoices("POSTGRES_USER"),
    )
    password: str = Field(
        default="",
        validation_alias=AliasChoices("POSTGRES_PASSWORD"),
    )
    database: str = Field(
        default="postgres",
        validation_alias=AliasChoices("POSTGRES_DB"),
    )

    strategy: str = Field(
        default="truncate",
        validation_alias=AliasChoices("GRAPH_BUILDER_STRATEGY"),
    )
    paper_top_k: int = Field(
        default=3,
        validation_alias=AliasChoices("GRAPH_BUILDER_PAPER_TOP_K"),
    )
    record_top_k: int = Field(
        default=2,
        validation_alias=AliasChoices("GRAPH_BUILDER_RECORD_TOP_K"),
    )
    paper_min_score: float = Field(
        default=0.02,
        validation_alias=AliasChoices("GRAPH_BUILDER_PAPER_MIN_SCORE"),
    )
    record_min_score: float = Field(
        default=0.02,
        validation_alias=AliasChoices("GRAPH_BUILDER_RECORD_MIN_SCORE"),
    )
