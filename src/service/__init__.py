"""Service modules."""

# Import refactored services (recommended for new code)
from service.query_service_refactored import QueryService, RetrievalContext
from service.schema_index_service_refactored import SchemaIndexService

# Keep backward compatibility with old service files
try:
    from service.query_service import (
        text2sql_pipeline,
        retrieve,
        generate_reasoning,
        generate_sql,
        fix_sql,
    )
    _HAS_OLD_SERVICES = True
except ImportError:
    _HAS_OLD_SERVICES = False

__all__ = [
    "QueryService",
    "RetrievalContext",
    "SchemaIndexService",
]

if _HAS_OLD_SERVICES:
    __all__.extend([
        "text2sql_pipeline",
        "retrieve",
        "generate_reasoning",
        "generate_sql",
        "fix_sql",
    ])

