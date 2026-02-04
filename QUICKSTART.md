# 快速开始指南

## 5 分钟快速上手

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

### 3. 构建索引（首次使用）

```bash
python examples/build_index.py
```

### 4. 测试查询

```bash
python examples/query_example.py
```

### 5. 启动 API 服务

```bash
python -m getDataFromWrenAI.main
```

访问 http://localhost:8000/docs 查看 API 文档。

## 使用示例

### Python 代码调用

```python
from getDataFromWrenAI.service import QueryService

# 创建服务
service = QueryService()

# 执行查询
result = service.text2sql("查询最近一周的订单数量")

# 查看结果
print(f"SQL: {result['final_sql']}")
print(f"结果: {result['rows']}")

# 关闭连接
service.close()
```

### API 调用

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "查询最近一周的订单数量"
  }'
```

## 常见问题

### Q: 如何添加 SQL 示例？

A: 在构建索引时传入 `sql_pairs` 参数：

```python
from getDataFromWrenAI.service import SchemaIndexService

service = SchemaIndexService()
service.build_sqlpair_index([
    {"question": "你的问题", "sql": "对应的SQL"}
])
service.close()
```

### Q: 如何修改配置？

A: 有两种方式：
1. 修改 `.env` 文件（推荐）
2. 在代码中直接修改 `Settings` 对象

### Q: 支持哪些数据库？

A: 目前支持 ClickHouse，其他数据库类型需要扩展实现。

## 下一步

- 查看 [README.md](README.md) 了解完整功能
- 查看 [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) 了解如何从旧版本迁移
- 查看 [OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md) 了解优化详情

