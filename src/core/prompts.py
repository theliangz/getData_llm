#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Prompt templates for SQL generation.
"""

from datetime import datetime
from typing import Optional

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

REASONING_SYSTEM_PROMPT = """
You are a senior data analyst.
You will be given:
- Database schema snippets
- SQL examples (question + SQL)
- A user question
- Current date and time information
Think step by step in natural language (NO SQL) how to answer the question.
"""

REASONING_USER_TEMPLATE = """
### CURRENT DATE AND TIME ###
{current_time}

### SCHEMA SNIPPETS (TOP-{k_schema}) ###
{schema_snippets}

### SQL EXAMPLES (TOP-{k_sql}) ###
{sql_examples}

### QUESTION ###
{question}

Provide a detailed reasoning plan in natural language ONLY (no SQL).
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
    elif db_type.lower() == "postgres":
        db_specific_rules = """
- PostgreSQL-specific: Use PostgreSQL functions and syntax.
- Use TO_DATE() for date parsing, TO_CHAR() for formatting.
- Use double quotes for identifiers, single quotes for strings.
"""
    elif db_type.lower() in ["mssql", "sqlserver"]:
        db_specific_rules = """
- SQL Server-specific: Use SQL Server functions and syntax.
- Use CONVERT() or CAST() for type conversions.
- Use square brackets [ ] for identifiers if needed.
"""
    elif db_type.lower() == "oracle":
        db_specific_rules = """
- Oracle-specific: Use Oracle functions and syntax.
- Use TO_DATE() for date parsing, TO_CHAR() for formatting.
- Use double quotes for identifiers, single quotes for strings.
"""
    
    return f"""
You are an expert {db_type_upper} SQL generator.
Follow the rules strictly.

{TEXT_TO_SQL_RULES}
{db_specific_rules}

Output only the SQL query.
"""


SQL_USER_TEMPLATE = """
### DATABASE TYPE ###
{db_type}

### CURRENT DATE AND TIME ###
{current_time}

### SCHEMA SNIPPETS (TOP-{k_schema}) ###
{schema_snippets}

### SQL EXAMPLES (TOP-{k_sql}) ###
{sql_examples}

### REASONING PLAN ###
{reasoning}

### QUESTION ###
{question}

Generate one valid {db_type_upper} SELECT query. Output only the SQL.
"""


def get_sql_fix_system_prompt(db_type: str = "clickhouse") -> str:
    """
    Get SQL fix system prompt for specific database type.
    
    Args:
        db_type: Database type
        
    Returns:
        SQL fix system prompt string
    """
    db_type_upper = db_type.upper()
    return f"""
You are an expert {db_type_upper} SQL fixer.
Given schema, examples, the original SQL, and an error type/message, return a corrected SQL.
Follow the rules.

{TEXT_TO_SQL_RULES}

Output only the corrected SQL.
"""


SQL_FIX_USER_TEMPLATE = """
### DATABASE TYPE ###
{db_type}

### CURRENT DATE AND TIME ###
{current_time}

### SCHEMA SNIPPETS (TOP-{k_schema}) ###
{schema_snippets}

### SQL EXAMPLES (TOP-{k_sql}) ###
{sql_examples}

### QUESTION ###
{question}

### ORIGINAL SQL ###
{sql}

### ERROR TYPE ###
{error_type}

### ERROR MESSAGE ###
{error_message}

Return the corrected SQL only.
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

