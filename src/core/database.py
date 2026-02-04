#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Database client for executing SQL queries.
Supports multiple database types: ClickHouse, MySQL, PostgreSQL, SQL Server, Oracle, SQLite.
"""

from typing import List, Tuple, Any, Optional
from urllib.parse import quote_plus

from config import get_settings
from utils import get_logger, DatabaseError

logger = get_logger(__name__)

# Try to import database drivers
try:
    import clickhouse_connect
    HAS_CLICKHOUSE = True
except ImportError:
    HAS_CLICKHOUSE = False

try:
    import pymysql
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

try:
    import psycopg2
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

try:
    import pyodbc
    HAS_MSSQL = True
except ImportError:
    HAS_MSSQL = False

try:
    import cx_Oracle
    HAS_ORACLE = True
except ImportError:
    HAS_ORACLE = False

try:
    import sqlite3
    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False


class DatabaseClient:
    """Database client for executing SQL queries."""
    
    def __init__(self, config=None):
        """Initialize database client."""
        settings = get_settings()
        self.config = config or settings.db
        self._client = None
        self._connection = None
        self._db_type = self.config.db_type.lower()
    
    def _get_connection_string(self) -> str:
        """Get database connection string based on type."""
        db_type = self._db_type
        
        if db_type == "clickhouse":
            # ClickHouse uses clickhouse_connect, not connection string
            return None
        elif db_type == "mysql":
            password = quote_plus(self.config.password) if self.config.password else ""
            return f"mysql+pymysql://{self.config.user}:{password}@{self.config.host}:{self.config.port}/{self.config.database}"
        elif db_type == "postgres":
            password = quote_plus(self.config.password) if self.config.password else ""
            return f"postgresql+psycopg2://{self.config.user}:{password}@{self.config.host}:{self.config.port}/{self.config.database}"
        elif db_type in ["mssql", "sqlserver"]:
            password = quote_plus(self.config.password) if self.config.password else ""
            return f"mssql+pyodbc://{self.config.user}:{password}@{self.config.host}:{self.config.port}/{self.config.database}?driver=ODBC+Driver+17+for+SQL+Server"
        elif db_type == "oracle":
            password = quote_plus(self.config.password) if self.config.password else ""
            return f"oracle+cx_oracle://{self.config.user}:{password}@{self.config.host}:{self.config.port or 1521}/{self.config.database}"
        elif db_type == "sqlite":
            return f"sqlite:///{self.config.database}"
        else:
            raise DatabaseError(f"Unsupported database type: {db_type}")
    
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
                
                elif self._db_type == "postgres":
                    if not HAS_POSTGRES:
                        raise DatabaseError("psycopg2-binary package is required for PostgreSQL support")
                    self._connection = psycopg2.connect(
                        host=self.config.host,
                        port=self.config.port,
                        user=self.config.user,
                        password=self.config.password,
                        database=self.config.database
                    )
                    logger.info(f"Connected to PostgreSQL at {self.config.host}:{self.config.port}")
                
                elif self._db_type in ["mssql", "sqlserver"]:
                    if not HAS_MSSQL:
                        raise DatabaseError("pyodbc package is required for SQL Server support")
                    conn_str = (
                        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                        f"SERVER={self.config.host},{self.config.port};"
                        f"DATABASE={self.config.database};"
                        f"UID={self.config.user};"
                        f"PWD={self.config.password}"
                    )
                    self._connection = pyodbc.connect(conn_str)
                    logger.info(f"Connected to SQL Server at {self.config.host}:{self.config.port}")
                
                elif self._db_type == "oracle":
                    if not HAS_ORACLE:
                        raise DatabaseError("cx_Oracle package is required for Oracle support")
                    dsn = cx_Oracle.makedsn(
                        self.config.host,
                        self.config.port or 1521,
                        service_name=self.config.database
                    )
                    self._connection = cx_Oracle.connect(
                        user=self.config.user,
                        password=self.config.password,
                        dsn=dsn
                    )
                    logger.info(f"Connected to Oracle at {self.config.host}:{self.config.port or 1521}")
                
                elif self._db_type == "sqlite":
                    if not HAS_SQLITE:
                        raise DatabaseError("sqlite3 is required for SQLite support (built-in)")
                    self._connection = sqlite3.connect(self.config.database)
                    logger.info(f"Connected to SQLite database: {self.config.database}")
                
                else:
                    raise DatabaseError(f"Unsupported database type: {self._db_type}")
                    
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise DatabaseError(f"Failed to connect to database: {e}") from e
        
        return self._client or self._connection
    
    def _is_aggregate_query(self, sql: str) -> bool:
        """
        Check if SQL is an aggregate query (COUNT, SUM, AVG, MAX, MIN, etc.).
        
        Args:
            sql: SQL query string
            
        Returns:
            True if query contains aggregate functions
        """
        sql_upper = sql.upper()
        # Common aggregate functions
        aggregate_patterns = [
            "COUNT(",
            "SUM(",
            "AVG(",
            "MAX(",
            "MIN(",
            "GROUP_CONCAT(",
            "STRING_AGG(",
            "ARRAY_AGG(",
        ]
        # Check for aggregate functions
        for pattern in aggregate_patterns:
            if pattern in sql_upper:
                return True
        # Check for GROUP BY clause (usually indicates aggregation)
        if "GROUP BY" in sql_upper:
            return True
        return False
    
    def _execute_with_cursor(self, sql: str) -> List[Tuple[Any, ...]]:
        """Execute SQL using cursor (for non-ClickHouse databases)."""
        cursor = self._connection.cursor()
        try:
            cursor.execute(sql)
            if cursor.description:
                rows = cursor.fetchall()
                # Convert dict rows to tuples if needed
                if isinstance(rows[0] if rows else None, dict):
                    rows = [tuple(row.values()) for row in rows]
                return rows
            else:
                return []
        finally:
            cursor.close()
    
    def execute(self, sql: str, limit: Optional[int] = None) -> List[Tuple[Any, ...]]:
        """
        Execute SQL query and return results.
        
        Args:
            sql: SQL query string
            limit: Optional limit for results (overrides query_limit config).
                   If None and query is not aggregate, will use config.query_limit.
                   If query is aggregate, limit will be ignored.
            
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
                # Aggregate query or already has LIMIT/TOP, use SQL as-is
                if is_aggregate:
                    logger.debug("Skipping LIMIT for aggregate query")
                sql_run = sql_strip
            
            logger.info(f"Executing SQL ({'aggregate' if is_aggregate else 'non-aggregate'}): {sql_run}")
            
            if self._db_type == "clickhouse":
                result = client.query(sql_run)
                rows = result.result_rows
                # Log actual result values for debugging
                if rows:
                    logger.debug(f"ClickHouse query result: {rows}")
                    logger.debug(f"First row values: {rows[0] if rows else 'empty'}")
            else:
                rows = self._execute_with_cursor(sql_run)
                # Log actual result values for debugging
                if rows:
                    logger.debug(f"Query result: {rows}")
                    logger.debug(f"First row values: {rows[0] if rows else 'empty'}")
            
            logger.info(f"Query executed successfully, returned {len(rows)} rows")
            if rows:
                logger.info(f"Result data: {rows}")
            return rows
        except Exception as e:
            logger.error(f"Failed to execute SQL: {e}")
            raise DatabaseError(f"Failed to execute SQL: {e}") from e
    
    def explain(self, sql: str) -> None:
        """
        Explain SQL query (validate syntax).
        
        Args:
            sql: SQL query string
            
        Raises:
            DatabaseError: If SQL is invalid
        """
        try:
            client = self._get_client()
            sql_strip = sql.strip().rstrip(";")
            logger.debug(f"Explaining SQL: {sql_strip}")
            
            if self._db_type == "clickhouse":
                client.query(f"EXPLAIN {sql_strip}")
            elif self._db_type == "mysql":
                self._execute_with_cursor(f"EXPLAIN {sql_strip}")
            elif self._db_type == "postgres":
                self._execute_with_cursor(f"EXPLAIN {sql_strip}")
            elif self._db_type in ["mssql", "sqlserver"]:
                self._execute_with_cursor(f"SET SHOWPLAN_ALL ON; {sql_strip}; SET SHOWPLAN_ALL OFF")
            elif self._db_type == "oracle":
                self._execute_with_cursor(f"EXPLAIN PLAN FOR {sql_strip}")
            elif self._db_type == "sqlite":
                self._execute_with_cursor(f"EXPLAIN QUERY PLAN {sql_strip}")
            
            logger.debug("SQL explanation successful")
        except Exception as e:
            logger.error(f"SQL explanation failed: {e}")
            raise DatabaseError(f"SQL explanation failed: {e}") from e
    
    def test_query(self, sql: str) -> bool:
        """
        Test query with LIMIT 1.
        
        Args:
            sql: SQL query string
            
        Returns:
            True if query executes successfully
        """
        try:
            client = self._get_client()
            sql_strip = sql.strip().rstrip(";")
            
            if self._db_type == "clickhouse":
                client.query(f"{sql_strip} LIMIT 1")
            elif self._db_type in ["mssql", "sqlserver"]:
                if sql_strip.upper().startswith("SELECT"):
                    test_sql = sql_strip.replace("SELECT", "SELECT TOP 1", 1)
                else:
                    test_sql = sql_strip
                self._execute_with_cursor(test_sql)
            elif self._db_type == "oracle":
                self._execute_with_cursor(f"{sql_strip} FETCH FIRST 1 ROWS ONLY")
            else:
                self._execute_with_cursor(f"{sql_strip} LIMIT 1")
            
            return True
        except Exception as e:
            logger.debug(f"Test query failed: {e}")
            return False
    
    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
        self._client = None

