# 迁移指南

本指南帮助您从旧版本的代码迁移到重构后的生产就绪版本。

## 主要变化

### 1. 代码结构重组

**旧结构:**
```
getDataFromWrenAI/
└── service/
    ├── query_service.py
    └── schema_index_service.py
```

**新结构:**
```
getDataFromWrenAI/
├── config/          # 配置管理
├── core/            # 核心业务逻辑
├── service/         # 服务层
├── api/             # API 层
└── utils/           # 工具模块
```

### 2. 配置管理

**旧方式:**
```python
# 直接在代码中使用 os.getenv()
LLM_CFG = LLMConfig()
```

**新方式:**
```python
from getDataFromWrenAI.config import get_settings

settings = get_settings()
# 使用 settings.llm.api_key 等
```

### 3. 服务使用

**旧方式:**
```python
from getDataFromWrenAI.service.query_service import text2sql_pipeline

result = text2sql_pipeline("查询问题")
```

**新方式:**
```python
from getDataFromWrenAI.service import QueryService

service = QueryService()
result = service.text2sql("查询问题")
service.close()
```

### 4. 索引构建

**旧方式:**
```python
from getDataFromWrenAI.service.schema_index_service import build_indexes

build_indexes(db_cfg, sql_pairs)
```

**新方式:**
```python
from getDataFromWrenAI.service import SchemaIndexService

service = SchemaIndexService()
service.build_indexes(sql_pairs=sql_pairs)
service.close()
```

## 迁移步骤

### 步骤 1: 更新依赖

安装新的依赖包：

```bash
pip install -r requirements.txt
```

### 步骤 2: 更新环境变量

创建 `.env` 文件（参考 `.env.example`），确保包含所有必要的配置。

### 步骤 3: 更新导入语句

将所有旧导入替换为新导入：

```python
# 旧
from getDataFromWrenAI.service.query_service import text2sql_pipeline

# 新
from getDataFromWrenAI.service import QueryService
```

### 步骤 4: 更新代码调用

按照上面的示例更新所有服务调用。

### 步骤 5: 测试

运行测试确保一切正常工作：

```bash
# 构建索引
python examples/build_index.py

# 测试查询
python examples/query_example.py

# 启动 API
python -m getDataFromWrenAI.main
```

## 兼容性说明

旧的服务文件 (`query_service.py` 和 `schema_index_service.py`) 仍然保留在项目中，但建议迁移到新的重构版本：

- `query_service.py` → `service/query_service_refactored.py`
- `schema_index_service.py` → `service/schema_index_service_refactored.py`

新版本提供了：
- 更好的错误处理
- 统一的日志系统
- 模块化设计
- API 接口
- 生产环境就绪

## 常见问题

### Q: 旧代码还能用吗？

A: 是的，旧代码仍然可以工作，但建议迁移到新版本以获得更好的维护性和功能。

### Q: 如何迁移现有的 Milvus 集合？

A: 新版本使用相同的集合名称（可通过环境变量配置），如果集合已存在，可以直接使用。如果需要重建，运行索引构建服务即可。

### Q: API 接口有什么变化？

A: 新版本提供了完整的 RESTful API，可以通过 HTTP 请求使用服务，而不仅仅是 Python 调用。

## 需要帮助？

如果遇到迁移问题，请查看：
1. README.md - 完整的使用文档
2. examples/ - 示例代码
3. 代码注释 - 详细的函数说明

