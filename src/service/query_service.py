#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：get_data 
@File    ：query_service.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2025/12/17 15:25 
'''
"""
查询服务：
- 从 Milvus 检索 schema 向量 + sql_pairs 向量
- reasoning → SQL 生成 → 诊断/try-run → 修正 → 执行
- 数据库连接可配置多类型（示例给出 clickhouse；其他类型需按 driver 实现 execute_sql/diagnose_sql）
"""

import os
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Literal

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from pymilvus import connections, Collection

# 若需 clickhouse，示例引入；其他库按需补充
import clickhouse_connect

load_dotenv()

# 配置
@dataclass
class LLMConfig:
    api_base: str = os.getenv("API_BASE_URL", "").rstrip("/")
    api_key: str = os.getenv("LLM_API_KEY", "")
    chat_model: str = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    embedding_model: str = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")

@dataclass
class MilvusConfig:
    host: str = os.getenv("MILVUS_HOST", "localhost")
    port: str = os.getenv("MILVUS_PORT", "19530")
    user: Optional[str] = os.getenv("MILVUS_USER")
    password: Optional[str] = os.getenv("MILVUS_PASSWORD")
    schema_collection: str = "schema_collection"
    sqlpair_collection: str = "sqlpair_collection"

@dataclass
class DBConfig:
    db_type: Literal["clickhouse", "postgres", "mysql", "mssql", "oracle", "sqlite"] = "clickhouse"
    host: str = "localhost"
    port: int = 8123
    user: str = "default"
    password: str = ""
    database: str = "default"
    secure: bool = False

LLM_CFG = LLMConfig()
MILVUS_CFG = MilvusConfig()
DB_CFG = DBConfig()

# OpenAI client
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

def chat_once(system_prompt: str, user_prompt: str, model: Optional[str] = None) -> str:
    client = get_openai_client()
    model = model or LLM_CFG.chat_model
    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
    )
    content = resp.choices[0].message.content or ""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        lines = content.splitlines()
        if lines and lines[0].strip().lower() in {"sql", ""}:
            lines = lines[1:]
        content = "\n".join(lines).strip()
    return content

# Milvus 检索
def connect_milvus():
    params = {"host": MILVUS_CFG.host, "port": MILVUS_CFG.port}
    if MILVUS_CFG.user and MILVUS_CFG.password:
        params["user"] = MILVUS_CFG.user
        params["password"] = MILVUS_CFG.password
    connections.connect("default", **params)

def milvus_search(collection_name: str, query_vec: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
    col = Collection(collection_name)
    search_params = {"metric_type": "IP", "params": {"nprobe": 64}}
    res = col.search(
        data=[query_vec.tolist()],
        anns_field="vector",
        param=search_params,
        limit=top_k,
        output_fields=["text", "meta"],
    )
    hits = res[0]
    return [{"text": h.entity.get("text"), "meta": h.entity.get("meta"), "score": h.distance} for h in hits]

# DB 连接 & 执行（示例：ClickHouse；其他需按 driver 实现）
def get_ch_client():
    return clickhouse_connect.get_client(
        host=DB_CFG.host,
        port=DB_CFG.port,
        username=DB_CFG.user,
        password=DB_CFG.password,
        database=DB_CFG.database,
        secure=DB_CFG.secure,
    )

def execute_sql(sql: str, limit: int = 100) -> List[Tuple[Any, ...]]:
    if DB_CFG.db_type != "clickhouse":
        raise NotImplementedError("执行示例仅实现 clickhouse；其他数据库请自行实现")
    client = get_ch_client()
    sql_strip = sql.strip().rstrip(";")
    if "limit" not in sql_strip.lower():
        sql_run = f"{sql_strip} LIMIT {limit}"
    else:
        sql_run = sql_strip
    return client.query(sql_run).result_rows

# 诊断
class SqlDiagnosisType:
    OK = "OK"
    ONLY_SELECT_ALLOWED = "ONLY_SELECT_ALLOWED"
    EXPLAIN_ERROR = "EXPLAIN_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"

@dataclass
class SqlDiagnosisResult:
    success: bool
    type: str
    message: str = ""

def diagnose_sql(sql: str) -> SqlDiagnosisResult:
    if DB_CFG.db_type != "clickhouse":
        raise NotImplementedError("诊断示例仅实现 clickhouse；其他数据库请自行实现")

    sql_strip = sql.strip().rstrip(";")
    if not sql_strip.lower().startswith("select"):
        return SqlDiagnosisResult(False, SqlDiagnosisType.ONLY_SELECT_ALLOWED, "Only SELECT statements are allowed.")

    client = get_ch_client()
    try:
        client.query(f"EXPLAIN {sql_strip}")
    except Exception as e:
        return SqlDiagnosisResult(False, SqlDiagnosisType.EXPLAIN_ERROR, str(e))

    try:
        client.query(f"{sql_strip} LIMIT 1")
        return SqlDiagnosisResult(True, SqlDiagnosisType.OK, "")
    except Exception as e:
        return SqlDiagnosisResult(False, SqlDiagnosisType.EXECUTION_ERROR, str(e))

# Prompt
TEXT_TO_SQL_RULES = """
### SQL RULES (HIGH PRIORITY) ###
- ONLY USE SELECT statements. DO NOT use INSERT, UPDATE, DELETE, ALTER, DROP, TRUNCATE or any DDL/DML.
- ONLY USE tables and columns that appear in the DATABASE SCHEMA section.
- DO NOT invent tables or columns that are not in the schema.
- Use double quotes for identifiers: "database"."table", "table"."column".
- Use single quotes for string literals. DO NOT quote numeric literals or functions.
- When joining multiple tables, ALWAYS specify explicit JOIN ... ON ... conditions.
- When using aggregation (SUM, COUNT, AVG, ...), put aggregate filters in HAVING, NOT in WHERE.
- If the user asks for a time period (e.g. a month), translate it into explicit date range conditions.
- Prefer using CTEs (WITH ...) instead of deeply nested subqueries.
- DO NOT include comments in the generated SQL.
- If unsure, choose the simplest valid SQL that best matches the question and schema.
"""

REASONING_SYSTEM_PROMPT = f"""
You are a senior data analyst.
You will be given:
- Database schema snippets
- SQL examples (question + SQL)
- A user question
Think step by step in natural language (NO SQL) how to answer the question.
"""

REASONING_USER_TEMPLATE = """
### SCHEMA SNIPPETS (TOP-{k_schema}) ###
{schema_snippets}

### SQL EXAMPLES (TOP-{k_sql}) ###
{sql_examples}

### QUESTION ###
{question}

Provide a detailed reasoning plan in natural language ONLY (no SQL).
"""

SQL_SYSTEM_PROMPT = f"""
You are an expert ClickHouse SQL generator.
Follow the rules strictly.

{TEXT_TO_SQL_RULES}

Output only the SQL query.
"""

SQL_USER_TEMPLATE = """
### SCHEMA SNIPPETS (TOP-{k_schema}) ###
{schema_snippets}

### SQL EXAMPLES (TOP-{k_sql}) ###
{sql_examples}

### REASONING PLAN ###
{reasoning}

### QUESTION ###
{question}

Generate one valid ClickHouse SELECT query. Output only the SQL.
"""

SQL_FIX_SYSTEM_PROMPT = f"""
You are an expert ClickHouse SQL fixer.
Given schema, examples, the original SQL, and an error type/message, return a corrected SQL.
Follow the rules.

{TEXT_TO_SQL_RULES}

Output only the corrected SQL.
"""

SQL_FIX_USER_TEMPLATE = """
### SCHEMA SNIPPETS (TOP-{k_schema}) ###
{schema_snippets}

### SQL EXAMPLES (TOP-{k_sql}) ###
{sql_examples}

### QUESTION ###
{question}

### ORIGINAL SQL ###
{sql}

### ERROR TYPE ###
{error_type}

### ERROR MESSAGE ###
{error_message}

Return the corrected SQL only.
"""

# 检索 + 生成 + 修正
@dataclass
class RetrievalContext:
    schema_snippets: List[str]
    sql_examples: List[str]

def retrieve(question: str, top_k_schema: int = 5, top_k_sql: int = 5) -> RetrievalContext:
    connect_milvus()
    q_vec = embed_texts([question])[0]
    schema_hits = milvus_search(MILVUS_CFG.schema_collection, q_vec, top_k=top_k_schema)
    sql_hits = milvus_search(MILVUS_CFG.sqlpair_collection, q_vec, top_k=top_k_sql) if MILVUS_CFG.sqlpair_collection else []

    schema_snippets = [h["text"] for h in schema_hits]
    sql_examples = [h["text"] for h in sql_hits]
    return RetrievalContext(schema_snippets, sql_examples)

def generate_reasoning(question: str, ctx: RetrievalContext) -> str:
    schema_text = "\n\n---\n\n".join(ctx.schema_snippets) if ctx.schema_snippets else "(no schema)"
    sql_text = "\n\n---\n\n".join(ctx.sql_examples) if ctx.sql_examples else "(no examples)"
    user_prompt = REASONING_USER_TEMPLATE.format(
        k_schema=len(ctx.schema_snippets),
        k_sql=len(ctx.sql_examples),
        schema_snippets=schema_text,
        sql_examples=sql_text,
        question=question,
    )
    return chat_once(REASONING_SYSTEM_PROMPT, user_prompt)

def generate_sql(question: str, ctx: RetrievalContext, reasoning: str) -> str:
    schema_text = "\n\n---\n\n".join(ctx.schema_snippets) if ctx.schema_snippets else "(no schema)"
    sql_text = "\n\n---\n\n".join(ctx.sql_examples) if ctx.sql_examples else "(no examples)"
    user_prompt = SQL_USER_TEMPLATE.format(
        k_schema=len(ctx.schema_snippets),
        k_sql=len(ctx.sql_examples),
        schema_snippets=schema_text,
        sql_examples=sql_text,
        reasoning=reasoning,
        question=question,
    )
    return chat_once(SQL_SYSTEM_PROMPT, user_prompt)

def fix_sql(question: str, ctx: RetrievalContext, original_sql: str, diag: SqlDiagnosisResult) -> str:
    schema_text = "\n\n---\n\n".join(ctx.schema_snippets) if ctx.schema_snippets else "(no schema)"
    sql_text = "\n\n---\n\n".join(ctx.sql_examples) if ctx.sql_examples else "(no examples)"
    user_prompt = SQL_FIX_USER_TEMPLATE.format(
        k_schema=len(ctx.schema_snippets),
        k_sql=len(ctx.sql_examples),
        schema_snippets=schema_text,
        sql_examples=sql_text,
        question=question,
        sql=original_sql,
        error_type=diag.type,
        error_message=diag.message,
    )
    return chat_once(SQL_FIX_SYSTEM_PROMPT, user_prompt)

def text2sql_pipeline(question: str, max_fix_rounds: int = 2) -> Dict[str, Any]:
    ctx = retrieve(question)
    reasoning = generate_reasoning(question, ctx)
    sql = generate_sql(question, ctx, reasoning)

    diag = diagnose_sql(sql)
    rounds = 0
    while not diag.success and rounds < max_fix_rounds:
        rounds += 1
        sql = fix_sql(question, ctx, sql, diag)
        diag = diagnose_sql(sql)

    result = {
        "question": question,
        "reasoning": reasoning,
        "final_sql": sql,
        "diagnosis": {"success": diag.success, "type": diag.type, "message": diag.message},
        "rows": [],
    }
    if diag.success:
        result["rows"] = execute_sql(sql)
    return result

# CLI
def main():
    print("Query Service with Milvus retrieval + reasoning + SQL gen + diagnose/fix")
    print("确保已运行 schema_index_service.build_indexes() 构建 Milvus 向量。")
    while True:
        q = input("\n问题> ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        out = text2sql_pipeline(q)
        print("\n[Reasoning]\n", out["reasoning"])
        print("\n[Final SQL]\n", out["final_sql"])
        print("\n[Diagnosis]\n", out["diagnosis"])
        if out["diagnosis"]["success"]:
            print("\n[Rows]\n", out["rows"][:5])

if __name__ == "__main__":
    main()


# 这套结构已经：
#
# - 按 **连接阶段 / 查询阶段** 做了清晰拆分；
# - schema 文档按 **表/列** 拆成细粒度向量；
# - 引入了 `sql_pairs` 的样例检索；
# - SQL 诊断返回 `SqlDiagnosisResult` 结构体，含 `type` 枚举；
# - 完整实现了 **检索 → reasoning → SQL 生成 → 诊断 + try-run → 修正 → 执行 SQL → 输出结果**。
#
# 你可以根据自己环境调整：
#
# - ClickHouse 表名（尤其是 `sql_pairs` 的结构）；
# - 使用的模型名（chat / embedding）；
# - 是否需要更多诊断类型（比如超时单独归类）。