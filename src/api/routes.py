#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
API routes for NL2SQL service.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from service import QueryService, SchemaIndexService
from utils import get_logger, NL2SQLError, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["nl2sql"])


# Request/Response models
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


class SQLPair(BaseModel):
    """SQL pair model for indexing."""
    question: str
    sql: str


class BuildIndexRequest(BaseModel):
    """Build index request model."""
    sql_pairs: Optional[List[SQLPair]] = Field(None, description="SQL example pairs")
    rebuild_schema: bool = Field(True, description="Whether to rebuild schema index")
    rebuild_sqlpair: bool = Field(True, description="Whether to rebuild SQL pair index")


class BuildIndexResponse(BaseModel):
    """Build index response model."""
    success: bool
    message: str
    schema_docs_count: Optional[int] = None
    sqlpair_docs_count: Optional[int] = None


# Dependency injection
def get_query_service() -> QueryService:
    """Get query service instance."""
    return QueryService()


def get_index_service() -> SchemaIndexService:
    """Get index service instance."""
    return SchemaIndexService()


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


@router.post("/build-index", response_model=BuildIndexResponse)
async def build_index(
    request: BuildIndexRequest,
    service: SchemaIndexService = Depends(get_index_service)
) -> BuildIndexResponse:
    """
    Build or rebuild vector indexes.
    
    Args:
        request: Build index request
        service: Index service instance
        
    Returns:
        Build index response
    """
    try:
        logger.info("Received build index request")
        
        sql_pairs = None
        if request.sql_pairs:
            sql_pairs = [{"question": p.question, "sql": p.sql} for p in request.sql_pairs]
        
        if request.rebuild_schema or request.rebuild_sqlpair:
            service.build_indexes(
                sql_pairs=sql_pairs if request.rebuild_sqlpair else None
            )
        
        return BuildIndexResponse(
            success=True,
            message="Indexes built successfully",
            schema_docs_count=None,  # Could be enhanced to return actual counts
            sqlpair_docs_count=len(sql_pairs) if sql_pairs else None
        )
    except NL2SQLError as e:
        logger.error(f"Index building error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        service.close()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "nl2sql"}

