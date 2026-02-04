#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Configuration settings management.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Literal
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """LLM configuration."""
    api_base: str = field(default_factory=lambda: os.getenv("API_BASE_URL", "").rstrip("/"))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    chat_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL_NAME", "gpt-4o-mini"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small"))
    temperature: float = 0.2
    max_tokens: Optional[int] = None


@dataclass
class MilvusConfig:
    """Milvus vector database configuration."""
    host: str = field(default_factory=lambda: os.getenv("MILVUS_HOST", "localhost"))
    port: str = field(default_factory=lambda: os.getenv("MILVUS_PORT", "19530"))
    user: Optional[str] = field(default_factory=lambda: os.getenv("MILVUS_USER"))
    password: Optional[str] = field(default_factory=lambda: os.getenv("MILVUS_PASSWORD"))
    schema_collection: str = field(default_factory=lambda: os.getenv("MILVUS_SCHEMA_COLLECTION", "schema_collection"))
    sqlpair_collection: str = field(default_factory=lambda: os.getenv("MILVUS_SQLPAIR_COLLECTION", "sqlpair_collection"))
    connection_alias: str = "default"
    search_metric: str = "IP"  # Inner Product
    search_nprobe: int = 64
    index_nlist: int = 1024


@dataclass
class DBConfig:
    """Database configuration."""
    db_type: Literal["clickhouse", "postgres", "mysql", "mssql", "oracle", "sqlite"] = field(
        default_factory=lambda: os.getenv("DB_TYPE", "clickhouse")
    )
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "8123")))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "default"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    database: str = field(default_factory=lambda: os.getenv("DB_DATABASE", "default"))
    secure: bool = field(default_factory=lambda: os.getenv("DB_SECURE", "false").lower() == "true")
    query_limit: int = 100  # Default limit for query results


@dataclass
class QueryConfig:
    """Query service configuration."""
    top_k_schema: int = 5
    top_k_sql: int = 5
    max_fix_rounds: int = 2
    enable_reasoning: bool = True


@dataclass
class Settings:
    """Application settings."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    milvus: MilvusConfig = field(default_factory=MilvusConfig)
    db: DBConfig = field(default_factory=DBConfig)
    query: QueryConfig = field(default_factory=QueryConfig)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "logs"))


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

