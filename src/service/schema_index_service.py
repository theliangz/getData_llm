#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：get_data 
@File    ：schema_index_service.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2025/12/17 15:24 
'''
"""
Part 1: 索引服务
- 连接 ClickHouse
- 抽取表/列 schema，按表/列拆成向量文档
- 从 sql_pairs 表读取 (question, sql) 样例
- 使用遵循 OpenAI 协议的 embedding 模型构建本地向量索引
- 将索引保存到本地目录，供查询服务加载

索引服务：
- 连接外部数据源
- 抽取数据库 schema（表/列，细粒度）
- 接收外部传入的 sql_pairs 列表
- 使用 OpenAI 协议的 embedding模型（从 .env 读取）
- 向量存储在 Milvus（pymilvus）
- 支持多数据库：clickhouse / postgres / mysql / mssql / oracle / sqlite
"""

import os
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Literal

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from pymilvus import (
    connections,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    utility,
)

# 环境与配置
load_dotenv()

@dataclass
class LLMConfig:
    api_base: str = os.getenv("API_BASE_URL", "").rstrip("/")
    api_key: str = os.getenv("LLM_API_KEY", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")

@dataclass
class MilvusConfig:
    host: str = os.getenv("MILVUS_HOST", "localhost")
    port: str = os.getenv("MILVUS_PORT", "19530")
    user: Optional[str] = os.getenv("MILVUS_USER")
    password: Optional[str] = os.getenv("MILVUS_PASSWORD")

@dataclass
class DBConfig:
    db_type: Literal["clickhouse", "postgres", "mysql", "mssql", "oracle", "sqlite"] = "clickhouse"
    host: str = os.getenv("CLICKHOUSE_HOST", "47.114.78.74")
    port: int = os.getenv("CLICKHOUSE_PORT", "19000")
    user: str = os.getenv("CLICKHOUSE_USER", "default")
    password: str = os.getenv("CLICKHOUSE_PASSWORD", "APS@a123")
    database: str = os.getenv("CLICKHOUSE_DATABASE", "acdmhfe")
    secure: bool = False  # clickhouse https 用

LLM_CFG = LLMConfig()
MILVUS_CFG = MilvusConfig()

# OpenAI Embedding
def get_openai_client() -> OpenAI:
    if not LLM_CFG.api_key:
        raise RuntimeError("缺少 LLM_API_KEY")
    if LLM_CFG.api_base:
        return OpenAI(api_key=LLM_CFG.api_key, base_url=LLM_CFG.api_base)
    return OpenAI(api_key=LLM_CFG.api_key)

def embed_texts(texts: List[str], model: Optional[str] = None) -> np.ndarray:
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    client = get_openai_client()
    model = model or LLM_CFG.embedding_model
    resp = client.embeddings.create(model=model, input=texts)
    vecs = [np.array(e.embedding, dtype=np.float32) for e in resp.data]
    return np.vstack(vecs)

# 数据库抽取
def load_schema_docs(db_cfg: DBConfig) -> List[Dict[str, Any]]:
    """
    返回列表，每个元素：
    {
      "text": "...schema snippet...",
      "meta": {...}
    }
    这里仍以 clickhouse 为例，其他库需扩展。
    """
    if db_cfg.db_type != "clickhouse":
        raise NotImplementedError("当前仅实现 clickhouse 抽取，其他驱动待扩展")

    import clickhouse_connect
    client = clickhouse_connect.get_client(
        host=db_cfg.host,
        port=db_cfg.port,
        username=db_cfg.user,
        password=db_cfg.password,
        database=db_cfg.database,
        secure=db_cfg.secure,
    )

    tables = client.query(
        """
        SELECT database, name
        FROM system.tables
        WHERE database = %(db)s
        ORDER BY database, name
        """,
        parameters={"db": db_cfg.database},
    ).result_rows

    docs: List[Dict[str, Any]] = []
    for db, table in tables:
        cols = client.query(
            """
            SELECT name, type, comment
            FROM system.columns
            WHERE database = %(db)s AND table = %(tbl)s
            ORDER BY position
            """,
            parameters={"db": db, "tbl": table},
        ).result_rows

        # 表级
        column_summaries = "\n".join(
            f'  - "{name}" {ctype}  # {comment}' if comment else f'  - "{name}" {ctype}'
            for name, ctype, comment in cols
        )
        table_text = f"""TABLE "{db}"."{table}"
        Columns:
        {column_summaries}
        """
        docs.append({"text": table_text, "meta": {"level": "table", "database": db, "table": table}})

        # 列级
        for name, ctype, comment in cols:
            col_text = f"""COLUMN "{db}"."{table}"."{name}"
            Type: {ctype}
            Comment: {comment or "N/A"}
            """
            docs.append(
                {
                    "text": col_text,
                    "meta": {
                        "level": "column",
                        "database": db,
                        "table": table,
                        "column": name,
                        "type": ctype,
                        "comment": comment or "",
                    },
                }
            )
    return docs

# Milvus 工具
def connect_milvus():
    params = {"host": MILVUS_CFG.host, "port": MILVUS_CFG.port}
    if MILVUS_CFG.user and MILVUS_CFG.password:
        params["user"] = MILVUS_CFG.user
        params["password"] = MILVUS_CFG.password
    connections.connect("default", **params)

def ensure_collection(name: str, dim: int) -> Collection:
    if utility.has_collection(name):
        col = Collection(name)
        # 简单假设维度一致；若不一致需要手动处理
        return col

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="meta", dtype=DataType.JSON),
    ]
    schema = CollectionSchema(fields, description=name)
    col = Collection(name, schema)
    col.create_index("vector", {"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 1024}})
    return col

def upsert_docs_to_milvus(collection: Collection, vectors: np.ndarray, texts: List[str], metas: List[Dict[str, Any]]):
    insert_data = [
        [None] * len(texts),  # auto_id
        vectors.tolist(),
        texts,
        metas,
    ]
    collection.insert(insert_data)
    collection.flush()

# 主入口
def build_indexes(
    db_cfg: DBConfig,
    sql_pairs: List[Dict[str, str]],  # 外部传入: [{"question": "...", "sql": "..."}]
    schema_collection_name: str = "schema_collection",
    sqlpair_collection_name: str = "sqlpair_collection",
):
    connect_milvus()

    # 1) schema 向量
    schema_docs = load_schema_docs(db_cfg)
    schema_texts = [d["text"] for d in schema_docs]
    schema_metas = [d["meta"] for d in schema_docs]
    schema_vecs = embed_texts(schema_texts)
    schema_dim = schema_vecs.shape[1] if schema_vecs.size else 1536
    schema_col = ensure_collection(schema_collection_name, schema_dim)
    upsert_docs_to_milvus(schema_col, schema_vecs, schema_texts, schema_metas)
    print(f"[schema] inserted {len(schema_texts)} docs into Milvus collection={schema_collection_name}")

    # 2) sql_pairs 向量（如果有）
    if sql_pairs:
        sql_texts = [f"SQL SAMPLE\nQuestion: {d['question']}\nSQL: {d['sql']}" for d in sql_pairs]
        sql_metas = sql_pairs
        sql_vecs = embed_texts(sql_texts)
        sql_dim = sql_vecs.shape[1] if sql_vecs.size else 1536
        sql_col = ensure_collection(sqlpair_collection_name, sql_dim)
        upsert_docs_to_milvus(sql_col, sql_vecs, sql_texts, sql_metas)
        print(f"[sql_pairs] inserted {len(sql_texts)} docs into Milvus collection={sqlpair_collection_name}")
    else:
        print("No sql_pairs provided, skip sqlpair_collection.")

if __name__ == "__main__":
    # 示例：外部传入 sql_pairs
    # demo_sql_pairs = [
    #     {"question": "查全国双机场城市", "sql": "SELECT sum(amount) FROM orders WHERE order_date >= today()-7"},
    # ]
    demo_sql_pairs = []
    db_cfg = DBConfig()
    build_indexes(db_cfg, demo_sql_pairs)