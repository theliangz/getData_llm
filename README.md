# getData

基于 LLM 和向量检索的 NL2SQL (Natural Language to SQL) 服务。

## 功能特性

-  **智能 SQL 生成**: 使用大语言模型将自然语言问题转换为 SQL 查询
-  **向量检索**: 使用 Milvus 向量数据库进行 schema 和 SQL 示例的相似度检索
-  **SQL 诊断与修复**: 自动诊断 SQL 错误并尝试修复
-  **多数据库支持**: 支持 ClickHouse、MySQL、PostgreSQL、SQL Server、Oracle、SQLite 等多种主流数据库
-  **时间感知**: 在 prompt 中自动注入当前时间信息，支持时间相关查询（如"查询上个月的数据"）
-  **生产就绪**: 模块化设计，完善的错误处理和日志系统

## 系统架构

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

工作流程：
1. 用户问题 → API 接收
2. 向量检索 → 从 Milvus 检索相关 schema 和 SQL 示例
3. 推理生成 → LLM 生成推理计划（包含当前时间信息）
4. SQL 生成 → LLM 生成 SQL（根据数据库类型和当前时间）
5. SQL 诊断 → 验证 SQL 语法和安全性
6. 自动修复 → 如有错误，尝试修复
7. 执行查询 → 在目标数据库执行 SQL
8. 返回结果 → 返回查询结果
```

## 项目结构

```
getDataFromWrenAI/
├── config/              # 配置模块
│   ├── __init__.py
│   └── settings.py      # 配置管理
├── core/                # 核心业务逻辑
│   ├── __init__.py
│   ├── llm_client.py    # LLM 客户端
│   ├── vector_store.py  # 向量数据库客户端
│   ├── database.py      # 数据库客户端（支持多数据库）
│   ├── sql_diagnosis.py # SQL 诊断
│   └── prompts.py       # Prompt 模板（支持动态数据库类型和时间）
├── service/             # 服务层
│   ├── __init__.py
│   ├── query_service_refactored.py      # 查询服务
│   └── schema_index_service_refactored.py # 索引服务
├── api/                 # API 层
│   ├── __init__.py
│   └── routes.py        # API 路由
├── utils/               # 工具模块
│   ├── __init__.py
│   ├── logger.py        # 日志工具
│   └── exceptions.py    # 异常定义
├── main.py              # 应用入口
└── __init__.py
```

## 安装

1. 克隆项目并安装依赖：

```bash
pip install -r requirements.txt
```

2. 配置环境变量（创建 `.env` 文件）：

```env
# LLM 配置
API_BASE_URL=https://your-llm-api.com
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=gpt-4o-mini
EMBEDDING_MODEL_NAME=text-embedding-3-small

# Milvus 配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=root
MILVUS_PASSWORD=your-password
MILVUS_SCHEMA_COLLECTION=schema_collection
MILVUS_SQLPAIR_COLLECTION=sqlpair_collection

# 数据库配置（支持多种数据库，只需修改 DB_TYPE）
# 支持的数据库类型: clickhouse, mysql, postgres, mssql, oracle, sqlite
DB_TYPE=clickhouse
DB_HOST=localhost
DB_PORT=8123
DB_USER=default
DB_PASSWORD=your-password
DB_DATABASE=your-database
DB_SECURE=false  # ClickHouse 专用，是否使用安全连接

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=logs
```

## 使用

### 1. 构建索引

首先需要构建 schema 和 SQL 示例的向量索引：

```python
from getDataFromWrenAI.service import SchemaIndexService

# 创建索引服务
index_service = SchemaIndexService()

# 构建索引
sql_pairs = [
    {"question": "查询所有用户", "sql": "SELECT * FROM users"},
    # 更多 SQL 示例...
]

index_service.build_indexes(sql_pairs=sql_pairs)
index_service.close()
```

### 2. 查询服务

使用查询服务进行 NL2SQL 转换：

```python
from getDataFromWrenAI.service import QueryService

# 创建查询服务
query_service = QueryService()

# 执行查询
result = query_service.text2sql("查询最近一周的订单数量")

print(f"生成的 SQL: {result['final_sql']}")
print(f"查询结果: {result['rows']}")

query_service.close()
```

### 3. API 服务

启动 API 服务：

```bash
python -m getDataFromWrenAI.main
```

或使用 uvicorn：

```bash
uvicorn getDataFromWrenAI.main:app --host 0.0.0.0 --port 8000
```

#### API 端点

- `POST /api/v1/query`: 执行 NL2SQL 查询
  ```json
  {
    "question": "查询最近一周的订单数量",
    "top_k_schema": 5,
    "top_k_sql": 5,
    "max_fix_rounds": 2
  }
  ```

- `POST /api/v1/build-index`: 构建向量索引
  ```json
  {
    "sql_pairs": [
      {"question": "查询所有用户", "sql": "SELECT * FROM users"}
    ],
    "rebuild_schema": true,
    "rebuild_sqlpair": true
  }
  ```

- `GET /api/v1/health`: 健康检查

## 工作流程

1. **向量检索**: 根据用户问题检索相关的 schema 片段和 SQL 示例
2. **推理生成**: 使用 LLM 生成推理计划（包含当前时间信息，支持时间相关查询）
3. **SQL 生成**: 基于检索结果、推理计划、数据库类型和当前时间生成 SQL
4. **SQL 诊断**: 验证 SQL 语法和安全性
5. **自动修复**: 如果 SQL 有错误，尝试自动修复（考虑数据库类型特性）
6. **执行查询**: 在目标数据库执行 SQL 并返回结果

### 时间感知功能

系统会自动在 prompt 中注入当前时间信息，包括：
- 当前日期和时间
- 星期几
- 月份和年份
- 周数

这使得系统能够理解时间相关的查询，例如：
- "查询上个月全国航班量"
- "查询本周的订单数据"
- "查询昨天的销售额"

## 配置说明

### LLM 配置

- `API_BASE_URL`: LLM API 基础 URL
- `LLM_API_KEY`: API 密钥
- `LLM_MODEL_NAME`: 聊天模型名称
- `EMBEDDING_MODEL_NAME`: 嵌入模型名称

### Milvus 配置

- `MILVUS_HOST`: Milvus 服务器地址
- `MILVUS_PORT`: Milvus 端口
- `MILVUS_SCHEMA_COLLECTION`: Schema 集合名称
- `MILVUS_SQLPAIR_COLLECTION`: SQL 示例集合名称

### 数据库配置

系统支持多种主流数据库，只需在 `.env` 文件中修改 `DB_TYPE` 即可切换数据库：

#### 支持的数据库类型

- **ClickHouse**: `DB_TYPE=clickhouse`
  - 默认端口: 8123
  - 需要安装: `clickhouse-connect`
  
- **MySQL**: `DB_TYPE=mysql`
  - 默认端口: 3306
  - 需要安装: `pymysql`
  
- **PostgreSQL**: `DB_TYPE=postgres`
  - 默认端口: 5432
  - 需要安装: `psycopg2-binary`
  
- **SQL Server**: `DB_TYPE=mssql` 或 `DB_TYPE=sqlserver`
  - 默认端口: 1433
  - 需要安装: `pyodbc`（需要系统安装 ODBC Driver）
  
- **Oracle**: `DB_TYPE=oracle`
  - 默认端口: 1521
  - 需要安装: `cx_Oracle`
  
- **SQLite**: `DB_TYPE=sqlite`
  - `DB_DATABASE` 应为 SQLite 文件路径
  - 内置支持，无需额外安装

#### 配置参数

- `DB_TYPE`: 数据库类型（clickhouse, mysql, postgres, mssql, oracle, sqlite）
- `DB_HOST`: 数据库主机地址
- `DB_PORT`: 数据库端口（SQLite 不需要）
- `DB_USER`: 数据库用户名（SQLite 不需要）
- `DB_PASSWORD`: 数据库密码（SQLite 不需要）
- `DB_DATABASE`: 数据库名称（SQLite 为文件路径）
- `DB_SECURE`: ClickHouse 专用，是否使用安全连接（true/false）

#### 示例配置

**ClickHouse:**
```env
DB_TYPE=clickhouse
DB_HOST=localhost
DB_PORT=8123
DB_USER=default
DB_PASSWORD=password
DB_DATABASE=default
DB_SECURE=false
```

**MySQL:**
```env
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=password
DB_DATABASE=mydb
```

**PostgreSQL:**
```env
DB_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=password
DB_DATABASE=mydb
```

**SQL Server:**
```env
DB_TYPE=mssql
DB_HOST=localhost
DB_PORT=1433
DB_USER=sa
DB_PASSWORD=password
DB_DATABASE=mydb
```

**SQLite:**
```env
DB_TYPE=sqlite
DB_DATABASE=/path/to/database.db
```

## 开发

### 代码结构说明

- **config/**: 配置管理，使用环境变量和默认值
- **core/**: 核心业务逻辑，包括 LLM、向量数据库、数据库客户端等
- **service/**: 服务层，封装业务逻辑
- **api/**: API 层，提供 RESTful 接口
- **utils/**: 工具模块，包括日志、异常等

### 数据库类型自动识别

系统会根据 `DB_TYPE` 环境变量自动：
1. 使用对应的数据库驱动进行连接
2. 在 SQL 生成 prompt 中告知 LLM 数据库类型
3. 根据数据库类型调整 SQL 语法（如 LIMIT vs TOP）
4. 使用数据库特定的函数和语法规则

### 扩展支持

系统已支持多种主流数据库。如需添加新的数据库类型：

1. 在 `core/database.py` 的 `_get_client()` 方法中添加连接逻辑
2. 在 `core/prompts.py` 的 `get_sql_system_prompt()` 中添加数据库特定的 SQL 规则
3. 更新 `config/settings.py` 中的 `DBConfig.db_type` 类型定义
4. 在 `requirements.txt` 中添加对应的数据库驱动包

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

