#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Refactored schema index service for building vector indexes.
"""

from typing import List, Dict, Any, Optional
import clickhouse_connect

from config import get_settings
from core import LLMClient, VectorStore
from utils import get_logger, NL2SQLError

logger = get_logger(__name__)


class SchemaIndexService:
    """Service for building schema and SQL example indexes."""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional[VectorStore] = None
    ):
        """Initialize schema index service."""
        self.settings = get_settings()
        self.llm_client = llm_client or LLMClient()
        self.vector_store = vector_store or VectorStore()
        self.vector_store.connect()
    
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
    
    def build_sqlpair_index(
        self,
        sql_pairs: List[Dict[str, str]],
        collection_name: Optional[str] = None
    ) -> None:
        """
        Build SQL example pair vector index.
        
        Args:
            sql_pairs: List of dicts with "question" and "sql" keys
            collection_name: Optional collection name override
        """
        if not sql_pairs:
            logger.info("No SQL pairs provided, skipping SQL pair index")
            return
        
        try:
            collection_name = collection_name or self.settings.milvus.sqlpair_collection
            logger.info(f"Building SQL pair index: {collection_name}")
            
            # Format SQL pair texts
            sql_texts = [
                f"SQL SAMPLE\nQuestion: {d['question']}\nSQL: {d['sql']}"
                for d in sql_pairs
            ]
            sql_metas = sql_pairs.copy()
            
            # Generate embeddings
            logger.info("Generating embeddings for SQL pairs")
            sql_vecs = self.llm_client.embed_texts(sql_texts)
            sql_dim = sql_vecs.shape[1] if sql_vecs.size else 1536
            
            # Ensure collection exists
            collection = self.vector_store.ensure_collection(collection_name, sql_dim)
            
            # Upsert documents
            self.vector_store.upsert(collection, sql_vecs, sql_texts, sql_metas)
            
            logger.info(f"SQL pair index built successfully: {len(sql_texts)} documents in {collection_name}")
        except Exception as e:
            logger.error(f"Failed to build SQL pair index: {e}")
            raise NL2SQLError(f"Failed to build SQL pair index: {e}") from e
    
    def build_indexes(
        self,
        sql_pairs: Optional[List[Dict[str, str]]] = None,
        schema_collection_name: Optional[str] = None,
        sqlpair_collection_name: Optional[str] = None,
        db_config=None
    ) -> None:
        """
        Build both schema and SQL pair indexes.
        
        Args:
            sql_pairs: Optional list of SQL example pairs
            schema_collection_name: Optional schema collection name override
            sqlpair_collection_name: Optional SQL pair collection name override
            db_config: Optional database config override
        """
        try:
            logger.info("Starting index building process")
            
            # Build schema index
            self.build_schema_index(schema_collection_name, db_config)
            
            # Build SQL pair index if provided
            if sql_pairs:
                self.build_sqlpair_index(sql_pairs, sqlpair_collection_name)
            
            logger.info("Index building completed successfully")
        except Exception as e:
            logger.error(f"Failed to build indexes: {e}")
            raise NL2SQLError(f"Failed to build indexes: {e}") from e
    
    def close(self):
        """Close connections."""
        self.vector_store.disconnect()

