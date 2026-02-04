#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Refactored query service for NL2SQL.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import get_settings
from core import LLMClient, VectorStore, DatabaseClient, SQLDiagnosis, SqlDiagnosisResult
from core.prompts import (
    REASONING_SYSTEM_PROMPT,
    REASONING_USER_TEMPLATE,
    get_sql_system_prompt,
    SQL_USER_TEMPLATE,
    get_sql_fix_system_prompt,
    SQL_FIX_USER_TEMPLATE,
    get_current_time_info,
)
from utils import get_logger, NL2SQLError

logger = get_logger(__name__)


@dataclass
class RetrievalContext:
    """Retrieval context from vector search."""
    schema_snippets: List[str]
    sql_examples: List[str]


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
                    if rows:
                        logger.info(f"Query result data: {rows}")
                        logger.info(f"First row: {rows[0] if rows else 'empty'}")
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
    
    def close(self):
        """Close connections."""
        self.vector_store.disconnect()

