# 基于LLM和向量检索的NL2SQL系统实战

## 一、项目概述

本项目是一个基于大语言模型（LLM）和向量检索技术的自然语言转SQL（NL2SQL）服务系统。该系统能够将用户的自然语言问题自动转换为SQL查询语句，并支持多种主流数据库（ClickHouse、MySQL、PostgreSQL、SQL Server、Oracle、SQLite等）。

### 核心特性

- **智能SQL生成**：使用大语言模型将自然语言问题转换为SQL查询
- **向量检索增强**：使用Milvus向量数据库进行schema和SQL示例的相似度检索
- **SQL诊断与修复**：自动诊断SQL错误并尝试修复
- **多数据库支持**：支持6种主流数据库，通过配置即可切换
- **时间感知**：在prompt中自动注入当前时间信息，支持时间相关查询
- **生产就绪**：模块化设计，完善的错误处理和日志系统

## 二、系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                      │
│                         (main.py)                                │
└────────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   API Routes   │
                    │  (routes.py)   │
                    └────────┬───────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │     Query Service            │
              │ (query_service_refactored.py) │
              └──────────┬────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ LLM Client   │  │Vector Store  │  │DB Client     │
│(llm_client)  │  │(Milvus)      │  │(Multi-DB)    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       │                 │                 │
       ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  OpenAI API  │  │  Milvus DB  │  │ClickHouse/   │
│  (Embedding  │  │  (Vector     │  │MySQL/Postgres│
│   & Chat)    │  │   Search)    │  │/MSSQL/etc.   │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 2.2 工作流程

1. **用户问题** → API接收自然语言问题
2. **向量检索** → 从Milvus检索相关schema和SQL示例
3. **推理生成** → LLM生成推理计划（包含当前时间信息）
4. **SQL生成** → LLM生成SQL（根据数据库类型和当前时间）
5. **SQL诊断** → 验证SQL语法和安全性
6. **自动修复** → 如有错误，尝试修复
7. **执行查询** → 在目标数据库执行SQL
8. **返回结果** → 返回查询结果

## 三、核心模块实现

### 3.1 配置管理模块

配置管理模块使用Python的`dataclass`和环境变量来管理所有配置项，支持通过`.env`文件进行配置。

```python
# src/config/settings.py

from dataclasses import dataclass, field
from typing import Optional, Literal
from functools import lru_cache
from dotenv import load_dotenv
import os

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
```

**设计亮点**：
- 使用`@lru_cache()`装饰器实现单例模式，避免重复创建配置对象
- 使用`dataclass`提供类型提示和默认值
- 支持环境变量和默认值的灵活配置

### 3.2 LLM客户端模块

LLM客户端封装了OpenAI API的调用，提供文本嵌入和聊天补全功能。

```python
# src/core/llm_client.py

from typing import List, Optional
import numpy as np
from openai import OpenAI
from config import get_settings
from utils import get_logger, LLMError

logger = get_logger(__name__)

class LLMClient:
    """LLM client wrapper."""
    
    def __init__(self, config=None):
        """Initialize LLM client."""
        settings = get_settings()
        self.config = config or settings.llm
        
        if not self.config.api_key:
            raise ValueError("LLM_API_KEY is required")
        
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client."""
        try:
            if self.config.api_base:
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.api_base
                )
            else:
                self._client = OpenAI(api_key=self.config.api_key)
            logger.info("LLM client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise LLMError(f"Failed to initialize LLM client: {e}") from e
    
    def embed_texts(self, texts: List[str], model: Optional[str] = None) -> np.ndarray:
        """
        Generate embeddings for texts.
        
        Args:
            texts: List of texts to embed
            model: Optional model name override
            
        Returns:
            numpy array of embeddings
        """
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        
        try:
            model = model or self.config.embedding_model
            logger.debug(f"Generating embeddings for {len(texts)} texts using model {model}")
            
            resp = self._client.embeddings.create(
                model=model,
                input=texts
            )
            
            vecs = [np.array(e.embedding, dtype=np.float32) for e in resp.data]
            result = np.vstack(vecs)
            logger.debug(f"Generated embeddings with shape {result.shape}")
            return result
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise LLMError(f"Failed to generate embeddings: {e}") from e
    
    def chat(self, system_prompt: str, user_prompt: str, model: Optional[str] = None, 
             temperature: Optional[float] = None) -> str:
        """
        Generate chat completion.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            model: Optional model name override
            temperature: Optional temperature override
            
        Returns:
            Generated text response
        """
        try:
            model = model or self.config.chat_model
            temperature = temperature if temperature is not None else self.config.temperature
            
            logger.debug(f"Generating chat completion using model {model}")
            
            resp = self._client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_prompt.strip()},
                ],
            )
            
            content = resp.choices[0].message.content or ""
            content = content.strip()
            
            # Clean up code blocks if present
            if content.startswith("```"):
                content = content.strip("`")
                lines = content.splitlines()
                if lines and lines[0].strip().lower() in {"sql", ""}:
                    lines = lines[1:]
                content = "\n".join(lines).strip()
            
            logger.debug(f"Generated response with length {len(content)}")
            return content
        except Exception as e:
            logger.error(f"Failed to generate chat completion: {e}")
            raise LLMError(f"Failed to generate chat completion: {e}") from e
```

**设计亮点**：
- 支持自定义API基础URL，可以对接不同的LLM服务
- 自动清理代码块标记，提取纯SQL代码
- 完善的错误处理和日志记录

### 3.3 向量存储模块

向量存储模块封装了Milvus向量数据库的操作，提供向量检索和索引构建功能。

```python
# src/core/vector_store.py

from typing import List, Dict, Any, Optional
import numpy as np
from pymilvus import connections, Collection, utility
from config import get_settings
from utils import get_logger, VectorDBError

logger = get_logger(__name__)

class VectorStore:
    """Vector store client for Milvus."""
    
    def __init__(self, config=None):
        """Initialize vector store client."""
        settings = get_settings()
        self.config = config or settings.milvus
        self._connected = False
    
    def connect(self) -> None:
        """Connect to Milvus."""
        if self._connected:
            return
        
        try:
            params = {
                "host": self.config.host,
                "port": self.config.port
            }
            if self.config.user and self.config.password:
                params["user"] = self.config.user
                params["password"] = self.config.password
            
            connections.connect(self.config.connection_alias, **params)
            self._connected = True
            logger.info(f"Connected to Milvus at {self.config.host}:{self.config.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise VectorDBError(f"Failed to connect to Milvus: {e}") from e
    
    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        top_k: int = 5,
        output_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search similar vectors in collection.
        
        Args:
            collection_name: Name of the collection
            query_vector: Query vector
            top_k: Number of results to return
            output_fields: Fields to return in results
            
        Returns:
            List of search results
        """
        if not self._connected:
            self.connect()
        
        try:
            collection = self.get_collection(collection_name)
            collection.load()
            
            search_params = {
                "metric_type": self.config.search_metric,
                "params": {"nprobe": self.config.search_nprobe}
            }
            
            output_fields = output_fields or ["text", "meta"]
            
            results = collection.search(
                data=[query_vector.tolist()],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                output_fields=output_fields,
            )
            
            hits = results[0]
            return [
                {
                    "text": hit.entity.get("text"),
                    "meta": hit.entity.get("meta"),
                    "score": hit.distance
                }
                for hit in hits
            ]
        except Exception as e:
            logger.error(f"Failed to search in collection {collection_name}: {e}")
            raise VectorDBError(f"Failed to search in collection {collection_name}: {e}") from e
    
    def ensure_collection(self, name: str, dim: int) -> Collection:
        """
        Ensure collection exists, create if not.
        
        Args:
            name: Collection name
            dim: Vector dimension
            
        Returns:
            Collection instance
        """
        if not self._connected:
            self.connect()
        
        try:
            if utility.has_collection(name):
                collection = Collection(name)
                logger.info(f"Collection {name} already exists")
                return collection
            
            from pymilvus import FieldSchema, CollectionSchema, DataType
            
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=60000),
                FieldSchema(name="meta", dtype=DataType.JSON),
            ]
            schema = CollectionSchema(fields, description=name)
            collection = Collection(name, schema)
            
            # Create index
            index_params = {
                "index_type": "IVF_FLAT",
                "metric_type": self.config.search_metric,
                "params": {"nlist": self.config.index_nlist}
            }
            collection.create_index("vector", index_params)
            
            logger.info(f"Created collection {name} with dimension {dim}")
            return collection
        except Exception as e:
            logger.error(f"Failed to ensure collection {name}: {e}")
            raise VectorDBError(f"Failed to ensure collection {name}: {e}") from e
```

**设计亮点**：
- 使用IVF_FLAT索引类型，平衡检索速度和精度
- 支持自动创建集合和索引
- 返回结果包含相似度分数，便于后续筛选

### 3.4 多数据库支持模块

数据库客户端模块实现了对多种数据库的统一接口，支持通过配置切换不同的数据库类型。

```python
# src/core/database.py (部分关键代码)

class DatabaseClient:
    """Database client for executing SQL queries."""
    
    def __init__(self, config=None):
        """Initialize database client."""
        settings = get_settings()
        self.config = config or settings.db
        self._client = None
        self._connection = None
        self._db_type = self.config.db_type.lower()
    
    def _get_client(self):
        """Get or create database client/connection."""
        if self._client is None and self._connection is None:
            try:
                if self._db_type == "clickhouse":
                    if not HAS_CLICKHOUSE:
                        raise DatabaseError("clickhouse-connect package is required for ClickHouse support")
                    self._client = clickhouse_connect.get_client(
                        host=self.config.host,
                        port=self.config.port,
                        username=self.config.user,
                        password=self.config.password,
                        database=self.config.database,
                        secure=self.config.secure,
                    )
                    logger.info(f"Connected to ClickHouse at {self.config.host}:{self.config.port}")
                
                elif self._db_type == "mysql":
                    if not HAS_MYSQL:
                        raise DatabaseError("pymysql package is required for MySQL support")
                    self._connection = pymysql.connect(
                        host=self.config.host,
                        port=self.config.port,
                        user=self.config.user,
                        password=self.config.password,
                        database=self.config.database,
                        cursorclass=pymysql.cursors.DictCursor
                    )
                    logger.info(f"Connected to MySQL at {self.config.host}:{self.config.port}")
                
                # ... 其他数据库类型的连接逻辑
                
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise DatabaseError(f"Failed to connect to database: {e}") from e
        
        return self._client or self._connection
    
    def execute(self, sql: str, limit: Optional[int] = None) -> List[Tuple[Any, ...]]:
        """
        Execute SQL query and return results.
        
        Args:
            sql: SQL query string
            limit: Optional limit for results
            
        Returns:
            List of result rows
        """
        try:
            client = self._get_client()
            sql_strip = sql.strip().rstrip(";")
            
            # Check if this is an aggregate query
            is_aggregate = self._is_aggregate_query(sql_strip)
            
            # For aggregate queries, don't add LIMIT automatically
            # For non-aggregate queries, add LIMIT if not present
            if not is_aggregate and "limit" not in sql_strip.lower() and "top" not in sql_strip.lower():
                limit = limit or self.config.query_limit
                logger.debug(f"Adding LIMIT {limit} to non-aggregate query")
                
                if self._db_type == "mssql" or self._db_type == "sqlserver":
                    # SQL Server uses TOP in SELECT
                    if sql_strip.upper().startswith("SELECT"):
                        sql_run = sql_strip.replace("SELECT", f"SELECT TOP {limit}", 1)
                    else:
                        sql_run = sql_strip
                elif self._db_type == "oracle":
                    # Oracle uses ROWNUM or FETCH FIRST
                    sql_run = f"{sql_strip} FETCH FIRST {limit} ROWS ONLY"
                else:
                    sql_run = f"{sql_strip} LIMIT {limit}"
            else:
                sql_run = sql_strip
            
            logger.info(f"Executing SQL ({'aggregate' if is_aggregate else 'non-aggregate'}): {sql_run}")
            
            if self._db_type == "clickhouse":
                result = client.query(sql_run)
                rows = result.result_rows
            else:
                rows = self._execute_with_cursor(sql_run)
            
            logger.info(f"Query executed successfully, returned {len(rows)} rows")
            return rows
        except Exception as e:
            logger.error(f"Failed to execute SQL: {e}")
            raise DatabaseError(f"Failed to execute SQL: {e}") from e
```

**设计亮点**：
- 统一的接口设计，屏蔽不同数据库的差异
- 智能识别聚合查询，避免对聚合查询添加LIMIT
- 根据数据库类型自动调整SQL语法（如SQL Server使用TOP，Oracle使用FETCH FIRST）

### 3.5 Prompt模板模块

Prompt模板模块定义了用于SQL生成的系统提示词和用户提示词模板，支持不同数据库类型和时间感知。

```python
# src/core/prompts.py (部分关键代码)

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
- IMPORTANT: If a date field (like "fdate") is of type UInt32 and contains Unix timestamp values (seconds since 1970-01-01), you MUST convert it to date format before comparison. Use toDate() or toDateTime() functions to convert Unix timestamps to dates.
- Prefer using CTEs (WITH ...) instead of deeply nested subqueries.
- DO NOT include comments in the generated SQL.
- If unsure, choose the simplest valid SQL that best matches the question and schema.
"""

def get_sql_system_prompt(db_type: str = "clickhouse") -> str:
    """
    Get SQL system prompt for specific database type.
    
    Args:
        db_type: Database type (clickhouse, mysql, postgres, mssql, etc.)
        
    Returns:
        SQL system prompt string
    """
    db_type_upper = db_type.upper()
    db_specific_rules = ""
    
    if db_type.lower() == "clickhouse":
        db_specific_rules = """
- ClickHouse-specific: Use ClickHouse functions and syntax.
- Use toDate() for date conversions, toDateTime() for datetime.
- Use formatDateTime() for date formatting.
- CRITICAL: If a date field is UInt32 type storing Unix timestamps (seconds since 1970-01-01), convert it using toDateTime(field) or toDate(toDateTime(field)) before date comparisons.
- Example: For field "fdate" (UInt32 Unix timestamp), use: toDate(toDateTime("fdate")) >= '2025-10-01' AND toDate(toDateTime("fdate")) <= '2025-10-31'
- When comparing dates, always convert Unix timestamp fields to Date type first, then compare with date strings like 'YYYY-MM-DD'.
"""
    elif db_type.lower() == "mysql":
        db_specific_rules = """
- MySQL-specific: Use MySQL functions and syntax.
- Use DATE_FORMAT() for date formatting, STR_TO_DATE() for parsing.
- Use backticks (`) for identifiers if needed.
"""
    # ... 其他数据库类型的特定规则
    
    return f"""
You are an expert {db_type_upper} SQL generator.
Follow the rules strictly.

{TEXT_TO_SQL_RULES}
{db_specific_rules}

Output only the SQL query.
"""

def get_current_time_info() -> str:
    """
    Get current date and time information for prompts.
    
    Returns:
        Formatted current time string
    """
    now = datetime.now()
    return f"""
Current Date: {now.strftime('%Y-%m-%d')}
Current Time: {now.strftime('%H:%M:%S')}
Current DateTime: {now.strftime('%Y-%m-%d %H:%M:%S')}
Day of Week: {now.strftime('%A')}
Week Number: {now.strftime('%U')}
Month: {now.strftime('%B')}
Year: {now.year}
"""
```

**设计亮点**：
- 针对不同数据库类型提供特定的SQL规则
- 自动注入当前时间信息，支持时间相关查询（如"查询上个月的数据"）
- 明确的规则约束，避免生成不安全的SQL

### 3.6 SQL诊断模块

SQL诊断模块负责验证SQL的语法和安全性，确保只执行SELECT语句。

```python
# src/core/sql_diagnosis.py

from dataclasses import dataclass
from typing import Optional
from core.database import DatabaseClient
from utils import get_logger

logger = get_logger(__name__)

class SqlDiagnosisType:
    """SQL diagnosis types."""
    OK = "OK"
    ONLY_SELECT_ALLOWED = "ONLY_SELECT_ALLOWED"
    EXPLAIN_ERROR = "EXPLAIN_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"

@dataclass
class SqlDiagnosisResult:
    """SQL diagnosis result."""
    success: bool
    type: str
    message: str = ""

class SQLDiagnosis:
    """SQL diagnosis service."""
    
    def __init__(self, db_client: Optional[DatabaseClient] = None):
        """Initialize SQL diagnosis service."""
        self.db_client = db_client or DatabaseClient()
    
    def diagnose(self, sql: str) -> SqlDiagnosisResult:
        """
        Diagnose SQL query.
        
        Args:
            sql: SQL query string
            
        Returns:
            SqlDiagnosisResult
        """
        sql_strip = sql.strip().rstrip(";")
        
        # Check if it's a SELECT statement
        if not sql_strip.lower().startswith("select"):
            logger.warning("Non-SELECT statement detected")
            return SqlDiagnosisResult(
                success=False,
                type=SqlDiagnosisType.ONLY_SELECT_ALLOWED,
                message="Only SELECT statements are allowed."
            )
        
        # Try EXPLAIN
        try:
            self.db_client.explain(sql_strip)
        except Exception as e:
            logger.warning(f"SQL EXPLAIN failed: {e}")
            return SqlDiagnosisResult(
                success=False,
                type=SqlDiagnosisType.EXPLAIN_ERROR,
                message=str(e)
            )
        
        # Try test execution
        if not self.db_client.test_query(sql_strip):
            logger.warning("SQL test execution failed")
            return SqlDiagnosisResult(
                success=False,
                type=SqlDiagnosisType.EXECUTION_ERROR,
                message="Query execution failed"
            )
        
        logger.info("SQL diagnosis passed")
        return SqlDiagnosisResult(
            success=True,
            type=SqlDiagnosisType.OK,
            message=""
        )
```

**设计亮点**：
- 三层验证：语句类型检查 → EXPLAIN验证 → 测试执行
- 使用EXPLAIN避免实际执行可能耗时的查询
- 使用LIMIT 1的测试查询进一步验证SQL有效性

### 3.7 查询服务模块

查询服务模块是整个系统的核心，实现了完整的NL2SQL流程。

```python
# src/service/query_service_refactored.py (核心方法)

class QueryService:
    """Query service for NL2SQL."""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional[VectorStore] = None,
        db_client: Optional[DatabaseClient] = None,
        sql_diagnosis: Optional[SQLDiagnosis] = None
    ):
        """Initialize query service."""
        self.settings = get_settings()
        self.llm_client = llm_client or LLMClient()
        self.vector_store = vector_store or VectorStore()
        self.db_client = db_client or DatabaseClient()
        self.sql_diagnosis = sql_diagnosis or SQLDiagnosis(self.db_client)
        
        # Connect vector store
        self.vector_store.connect()
    
    def retrieve(self, question: str, top_k_schema: Optional[int] = None, 
                 top_k_sql: Optional[int] = None) -> RetrievalContext:
        """
        Retrieve relevant schema and SQL examples.
        
        Args:
            question: User question
            top_k_schema: Number of schema snippets to retrieve
            top_k_sql: Number of SQL examples to retrieve
            
        Returns:
            RetrievalContext with schema snippets and SQL examples
        """
        top_k_schema = top_k_schema or self.settings.query.top_k_schema
        top_k_sql = top_k_sql or self.settings.query.top_k_sql
        
        try:
            logger.info(f"Retrieving context for question: {question[:50]}...")
            
            # Generate query embedding
            query_vec = self.llm_client.embed_texts([question])[0]
            
            # Search schema collection
            schema_hits = self.vector_store.search(
                collection_name=self.settings.milvus.schema_collection,
                query_vector=query_vec,
                top_k=top_k_schema
            )
            
            # Search SQL examples collection
            sql_hits = []
            if self.settings.milvus.sqlpair_collection:
                sql_hits = self.vector_store.search(
                    collection_name=self.settings.milvus.sqlpair_collection,
                    query_vector=query_vec,
                    top_k=top_k_sql
                )
            
            schema_snippets = [h["text"] for h in schema_hits]
            sql_examples = [h["text"] for h in sql_hits]
            
            logger.info(f"Retrieved {len(schema_snippets)} schema snippets and {len(sql_examples)} SQL examples")
            
            return RetrievalContext(
                schema_snippets=schema_snippets,
                sql_examples=sql_examples
            )
        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
            raise NL2SQLError(f"Failed to retrieve context: {e}") from e
    
    def generate_reasoning(self, question: str, ctx: RetrievalContext) -> str:
        """
        Generate reasoning plan.
        
        Args:
            question: User question
            ctx: Retrieval context
            
        Returns:
            Reasoning plan text
        """
        try:
            schema_text = "\n\n---\n\n".join(ctx.schema_snippets) if ctx.schema_snippets else "(no schema)"
            sql_text = "\n\n---\n\n".join(ctx.sql_examples) if ctx.sql_examples else "(no examples)"
            current_time = get_current_time_info()
            
            user_prompt = REASONING_USER_TEMPLATE.format(
                k_schema=len(ctx.schema_snippets),
                k_sql=len(ctx.sql_examples),
                schema_snippets=schema_text,
                sql_examples=sql_text,
                question=question,
                current_time=current_time,
            )
            
            logger.debug("Generating reasoning plan")
            reasoning = self.llm_client.chat(REASONING_SYSTEM_PROMPT, user_prompt)
            logger.debug(f"Generated reasoning plan: {reasoning[:100]}...")
            return reasoning
        except Exception as e:
            logger.error(f"Failed to generate reasoning: {e}")
            raise NL2SQLError(f"Failed to generate reasoning: {e}") from e
    
    def generate_sql(self, question: str, ctx: RetrievalContext, reasoning: str) -> str:
        """
        Generate SQL from question and context.
        
        Args:
            question: User question
            ctx: Retrieval context
            reasoning: Reasoning plan
            
        Returns:
            Generated SQL query
        """
        try:
            db_type = self.settings.db.db_type
            schema_text = "\n\n---\n\n".join(ctx.schema_snippets) if ctx.schema_snippets else "(no schema)"
            sql_text = "\n\n---\n\n".join(ctx.sql_examples) if ctx.sql_examples else "(no examples)"
            current_time = get_current_time_info()
            
            user_prompt = SQL_USER_TEMPLATE.format(
                db_type=db_type,
                db_type_upper=db_type.upper(),
                k_schema=len(ctx.schema_snippets),
                k_sql=len(ctx.sql_examples),
                schema_snippets=schema_text,
                sql_examples=sql_text,
                reasoning=reasoning,
                question=question,
                current_time=current_time,
            )
            
            system_prompt = get_sql_system_prompt(db_type)
            
            logger.debug(f"Generating SQL for {db_type}")
            sql = self.llm_client.chat(system_prompt, user_prompt)
            logger.info(f"Generated SQL: {sql[:100]}...")
            return sql
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            raise NL2SQLError(f"Failed to generate SQL: {e}") from e
    
    def fix_sql(self, question: str, ctx: RetrievalContext, original_sql: str, 
                diag: SqlDiagnosisResult) -> str:
        """
        Fix SQL based on diagnosis result.
        
        Args:
            question: User question
            ctx: Retrieval context
            original_sql: Original SQL that failed
            diag: Diagnosis result
            
        Returns:
            Fixed SQL query
        """
        try:
            db_type = self.settings.db.db_type
            schema_text = "\n\n---\n\n".join(ctx.schema_snippets) if ctx.schema_snippets else "(no schema)"
            sql_text = "\n\n---\n\n".join(ctx.sql_examples) if ctx.sql_examples else "(no examples)"
            current_time = get_current_time_info()
            
            user_prompt = SQL_FIX_USER_TEMPLATE.format(
                db_type=db_type,
                k_schema=len(ctx.schema_snippets),
                k_sql=len(ctx.sql_examples),
                schema_snippets=schema_text,
                sql_examples=sql_text,
                question=question,
                sql=original_sql,
                error_type=diag.type,
                error_message=diag.message,
                current_time=current_time,
            )
            
            system_prompt = get_sql_fix_system_prompt(db_type)
            
            logger.debug(f"Fixing SQL with error type: {diag.type}")
            fixed_sql = self.llm_client.chat(system_prompt, user_prompt)
            logger.info(f"Fixed SQL: {fixed_sql[:100]}...")
            return fixed_sql
        except Exception as e:
            logger.error(f"Failed to fix SQL: {e}")
            raise NL2SQLError(f"Failed to fix SQL: {e}") from e
    
    def text2sql(self, question: str, max_fix_rounds: Optional[int] = None) -> Dict[str, Any]:
        """
        Complete NL2SQL pipeline.
        
        Args:
            question: User question in natural language
            max_fix_rounds: Maximum number of fix attempts
            
        Returns:
            Dictionary with question, reasoning, SQL, diagnosis, and results
        """
        max_fix_rounds = max_fix_rounds or self.settings.query.max_fix_rounds
        
        try:
            logger.info(f"Starting NL2SQL pipeline for question: {question[:50]}...")
            
            # Step 1: Retrieve context
            ctx = self.retrieve(question)
            
            # Step 2: Generate reasoning (if enabled)
            reasoning = ""
            if self.settings.query.enable_reasoning:
                reasoning = self.generate_reasoning(question, ctx)
            
            # Step 3: Generate SQL
            sql = self.generate_sql(question, ctx, reasoning)
            
            # Step 4: Diagnose and fix if needed
            diag = self.sql_diagnosis.diagnose(sql)
            rounds = 0
            while not diag.success and rounds < max_fix_rounds:
                rounds += 1
                logger.info(f"Fixing SQL (attempt {rounds}/{max_fix_rounds})")
                sql = self.fix_sql(question, ctx, sql, diag)
                diag = self.sql_diagnosis.diagnose(sql)
            
            # Step 5: Execute SQL if valid
            result = {
                "question": question,
                "reasoning": reasoning,
                "final_sql": sql,
                "diagnosis": {
                    "success": diag.success,
                    "type": diag.type,
                    "message": diag.message
                },
                "data_result": [],
            }
            
            if diag.success:
                try:
                    rows = self.db_client.execute(sql)
                    result["data_result"] = rows
                    logger.info(f"Query executed successfully, returned {len(rows)} rows")
                except Exception as e:
                    logger.error(f"Failed to execute SQL: {e}")
                    result["diagnosis"]["success"] = False
                    result["diagnosis"]["message"] = str(e)
            else:
                logger.warning(f"SQL diagnosis failed: {diag.message}")
            
            return result
        except Exception as e:
            logger.error(f"NL2SQL pipeline failed: {e}")
            raise NL2SQLError(f"NL2SQL pipeline failed: {e}") from e
```

**设计亮点**：
- 完整的NL2SQL流程：检索 → 推理 → 生成 → 诊断 → 修复 → 执行
- 支持多轮修复，提高SQL生成成功率
- 模块化设计，每个步骤都可以独立测试和优化

### 3.8 索引服务模块

索引服务模块负责构建schema和SQL示例的向量索引。

```python
# src/service/schema_index_service_refactored.py (部分关键代码)

class SchemaIndexService:
    """Service for building schema and SQL example indexes."""
    
    def load_schema_docs(self, db_config=None) -> List[Dict[str, Any]]:
        """
        Load schema documents from database.
        
        Args:
            db_config: Optional database config override
            
        Returns:
            List of schema documents with text and metadata
        """
        db_config = db_config or self.settings.db
        
        if db_config.db_type != "clickhouse":
            raise NotImplementedError(
                f"Database type {db_config.db_type} is not yet implemented. "
                "Only ClickHouse is currently supported."
            )
        
        try:
            logger.info(f"Loading schema from ClickHouse database: {db_config.database}")
            
            client = clickhouse_connect.get_client(
                host=db_config.host,
                port=db_config.port,
                username=db_config.user,
                password=db_config.password,
                database=db_config.database,
                secure=db_config.secure,
            )
            
            # Get all tables
            tables = client.query(
                """
                SELECT database, name
                FROM system.tables
                WHERE database = %(db)s
                ORDER BY database, name
                """,
                parameters={"db": db_config.database},
            ).result_rows
            
            docs: List[Dict[str, Any]] = []
            
            for db, table in tables:
                # Get columns for this table
                cols = client.query(
                    """
                    SELECT name, type, comment
                    FROM system.columns
                    WHERE database = %(db)s AND table = %(tbl)s
                    ORDER BY position
                    """,
                    parameters={"db": db, "tbl": table},
                ).result_rows
                
                # Table-level document
                column_summaries = "\n".join(
                    f'  - "{name}" {ctype}  # {comment}' if comment else f'  - "{name}" {ctype}'
                    for name, ctype, comment in cols
                )
                table_text = f"""TABLE "{db}"."{table}"
Columns:
{column_summaries}
"""
                docs.append({
                    "text": table_text,
                    "meta": {
                        "level": "table",
                        "database": db,
                        "table": table
                    }
                })
                
                # Column-level documents
                for name, ctype, comment in cols:
                    col_text = f"""COLUMN "{db}"."{table}"."{name}"
Type: {ctype}
Comment: {comment or "N/A"}
"""
                    docs.append({
                        "text": col_text,
                        "meta": {
                            "level": "column",
                            "database": db,
                            "table": table,
                            "column": name,
                            "type": ctype,
                            "comment": comment or "",
                        }
                    })
            
            logger.info(f"Loaded {len(docs)} schema documents from {len(tables)} tables")
            return docs
        except Exception as e:
            logger.error(f"Failed to load schema documents: {e}")
            raise NL2SQLError(f"Failed to load schema documents: {e}") from e
    
    def build_schema_index(
        self,
        collection_name: Optional[str] = None,
        db_config=None
    ) -> None:
        """
        Build schema vector index.
        
        Args:
            collection_name: Optional collection name override
            db_config: Optional database config override
        """
        try:
            collection_name = collection_name or self.settings.milvus.schema_collection
            logger.info(f"Building schema index: {collection_name}")
            
            # Load schema documents
            schema_docs = self.load_schema_docs(db_config)
            
            if not schema_docs:
                logger.warning("No schema documents found")
                return
            
            # Extract texts and metadata
            schema_texts = [d["text"] for d in schema_docs]
            schema_metas = [d["meta"] for d in schema_docs]
            
            # Generate embeddings
            logger.info("Generating embeddings for schema documents")
            schema_vecs = self.llm_client.embed_texts(schema_texts)
            schema_dim = schema_vecs.shape[1] if schema_vecs.size else 1536
            
            # Ensure collection exists
            collection = self.vector_store.ensure_collection(collection_name, schema_dim)
            
            # Upsert documents
            self.vector_store.upsert(collection, schema_vecs, schema_texts, schema_metas)
            
            logger.info(f"Schema index built successfully: {len(schema_texts)} documents in {collection_name}")
        except Exception as e:
            logger.error(f"Failed to build schema index: {e}")
            raise NL2SQLError(f"Failed to build schema index: {e}") from e
```

**设计亮点**：
- 支持表级和列级两种粒度的schema文档
- 自动从数据库系统表提取schema信息
- 批量生成嵌入向量，提高索引构建效率

### 3.9 API路由模块

API路由模块提供RESTful接口，方便外部系统调用。

```python
# src/api/routes.py (部分关键代码)

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from service import QueryService, SchemaIndexService
from utils import get_logger, NL2SQLError, setup_logging

setup_logging()
logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["nl2sql"])

class QueryRequest(BaseModel):
    """Query request model."""
    question: str = Field(..., description="Natural language question")
    top_k_schema: Optional[int] = Field(None, description="Number of schema snippets to retrieve")
    top_k_sql: Optional[int] = Field(None, description="Number of SQL examples to retrieve")
    max_fix_rounds: Optional[int] = Field(None, description="Maximum number of SQL fix attempts")

class QueryResponse(BaseModel):
    """Query response model."""
    question: str
    reasoning: str
    final_sql: str
    diagnosis: Dict[str, Any]
    data_result: List[Any] = Field(..., description="Query result data from database")
    success: bool

@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service)
) -> QueryResponse:
    """
    Convert natural language to SQL and execute.
    
    Args:
        request: Query request
        service: Query service instance
        
    Returns:
        Query response with SQL and results
    """
    try:
        logger.info(f"Received query request: {request.question[:50]}...")
        
        result = service.text2sql(
            question=request.question,
            max_fix_rounds=request.max_fix_rounds
        )
        
        return QueryResponse(
            question=result["question"],
            reasoning=result["reasoning"],
            final_sql=result["final_sql"],
            diagnosis=result["diagnosis"],
            data_result=result["data_result"],
            success=result["diagnosis"]["success"]
        )
    except NL2SQLError as e:
        logger.error(f"NL2SQL error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        service.close()
```

**设计亮点**：
- 使用FastAPI的依赖注入管理服务实例
- 完善的错误处理和HTTP状态码
- 使用Pydantic模型进行请求和响应验证

## 四、关键技术点解析

### 4.1 向量检索增强生成

传统的LLM生成SQL往往需要完整的schema信息，这在大型数据库中会导致prompt过长。本项目采用向量检索技术，只检索与用户问题最相关的schema片段和SQL示例，大大减少了prompt的长度，提高了生成质量。

**实现原理**：
1. 将schema和SQL示例转换为向量嵌入
2. 将用户问题也转换为向量嵌入
3. 使用向量相似度检索最相关的top-k个schema和SQL示例
4. 将这些检索结果作为上下文提供给LLM生成SQL

### 4.2 多数据库适配策略

不同数据库的SQL语法存在差异，本项目通过以下策略实现多数据库支持：

1. **配置驱动**：通过环境变量`DB_TYPE`指定数据库类型
2. **动态连接**：根据数据库类型使用对应的驱动库
3. **SQL语法适配**：在prompt中告知LLM数据库类型，并提供特定规则
4. **LIMIT语法适配**：自动将LIMIT转换为对应数据库的语法（如SQL Server的TOP，Oracle的FETCH FIRST）

### 4.3 时间感知功能

系统自动在prompt中注入当前时间信息，使得LLM能够理解时间相关的自然语言查询。

**时间信息包括**：
- 当前日期和时间
- 星期几
- 月份和年份
- 周数

**应用场景**：
- "查询上个月全国航班量" → 自动计算上个月的日期范围
- "查询本周的订单数据" → 自动计算本周的日期范围
- "查询昨天的销售额" → 自动计算昨天的日期

### 4.4 SQL诊断与自动修复

系统实现了三层SQL验证机制：

1. **语句类型检查**：确保只允许SELECT语句
2. **EXPLAIN验证**：使用数据库的EXPLAIN功能验证SQL语法
3. **测试执行**：使用LIMIT 1执行测试查询

如果SQL验证失败，系统会将错误信息反馈给LLM，让LLM根据错误信息修复SQL，最多尝试N轮（可配置）。

### 4.5 聚合查询智能识别

系统能够智能识别聚合查询（包含COUNT、SUM、AVG等聚合函数或GROUP BY子句），对于聚合查询不自动添加LIMIT，避免影响查询结果的正确性。

## 五、使用示例

### 5.1 构建索引

首先需要构建schema和SQL示例的向量索引：

```python
from src.service import SchemaIndexService

# 创建索引服务
index_service = SchemaIndexService()

# 构建索引
sql_pairs = [
    {"question": "查询所有用户", "sql": "SELECT * FROM users"},
    {"question": "查询最近一周的订单数量", "sql": "SELECT COUNT(*) FROM orders WHERE order_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"},
    # 更多 SQL 示例...
]

index_service.build_indexes(sql_pairs=sql_pairs)
index_service.close()
```

### 5.2 执行查询

使用查询服务进行NL2SQL转换：

```python
from src.service import QueryService

# 创建查询服务
query_service = QueryService()

# 执行查询
result = query_service.text2sql("查询最近一周的订单数量")

print(f"生成的 SQL: {result['final_sql']}")
print(f"查询结果: {result['data_result']}")

query_service.close()
```

### 5.3 API调用

启动API服务后，可以通过HTTP接口调用：

```bash
# 启动服务
python -m src.main

# 调用查询接口
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "查询最近一周的订单数量",
    "top_k_schema": 5,
    "top_k_sql": 5,
    "max_fix_rounds": 2
  }'
```

## 六、项目优势与创新点

### 6.1 技术优势

1. **模块化设计**：各模块职责清晰，易于维护和扩展
2. **多数据库支持**：通过配置即可切换不同数据库，无需修改代码
3. **向量检索增强**：提高SQL生成质量，减少prompt长度
4. **自动修复机制**：提高SQL生成成功率
5. **时间感知**：支持自然语言中的时间相关查询

### 6.2 创新点

1. **双层检索**：同时检索schema和SQL示例，提供更丰富的上下文
2. **推理+生成两阶段**：先让LLM生成推理计划，再生成SQL，提高准确性
3. **数据库类型感知**：在prompt中动态注入数据库特定规则
4. **智能LIMIT处理**：自动识别聚合查询，避免错误添加LIMIT

## 七、性能优化建议

1. **向量检索优化**：
   - 调整`top_k_schema`和`top_k_sql`参数，平衡检索质量和prompt长度
   - 使用更高效的向量索引类型（如HNSW）

2. **LLM调用优化**：
   - 使用流式响应减少等待时间
   - 缓存常见问题的SQL结果
   - 使用更小的模型进行简单查询

3. **数据库连接优化**：
   - 使用连接池管理数据库连接
   - 对查询结果进行分页处理

4. **索引构建优化**：
   - 增量更新索引，避免全量重建
   - 并行处理多个文档的嵌入生成

## 八、总结

本项目实现了一个完整的NL2SQL系统，结合了LLM的强大生成能力和向量检索的精准匹配能力。通过模块化设计、多数据库支持、自动修复等特性，使得系统既灵活又可靠。该系统可以广泛应用于BI分析、数据查询、报表生成等场景，大大降低了非技术人员使用数据库的门槛。

### 关键技术栈

- **Web框架**：FastAPI
- **LLM**：OpenAI API（支持自定义API）
- **向量数据库**：Milvus
- **数据库支持**：ClickHouse、MySQL、PostgreSQL、SQL Server、Oracle、SQLite
- **Python版本**：3.8+

### 未来改进方向

1. 支持更多数据库类型
2. 实现增量索引更新
3. 添加查询结果缓存
4. 支持多轮对话上下文
5. 添加查询性能分析
6. 支持自定义函数和视图

---

*本文档详细介绍了基于LLM和向量检索的NL2SQL系统的完整实现方法，包括架构设计、核心模块实现、关键技术点解析等。希望本文档能够帮助读者理解NL2SQL系统的实现原理，并为类似项目的开发提供参考。*


