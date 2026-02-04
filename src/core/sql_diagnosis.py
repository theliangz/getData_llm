#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
SQL diagnosis and validation.
"""

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
    
    def __str__(self) -> str:
        return f"SqlDiagnosisResult(success={self.success}, type={self.type}, message={self.message})"


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

