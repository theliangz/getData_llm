#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Custom exceptions for NL2SQL service.
"""


class NL2SQLError(Exception):
    """Base exception for NL2SQL service."""
    pass


class ConfigurationError(NL2SQLError):
    """Configuration related errors."""
    pass


class DatabaseError(NL2SQLError):
    """Database operation errors."""
    pass


class VectorDBError(NL2SQLError):
    """Vector database operation errors."""
    pass


class LLMError(NL2SQLError):
    """LLM API errors."""
    pass


class SQLGenerationError(NL2SQLError):
    """SQL generation errors."""
    pass


class SQLExecutionError(NL2SQLError):
    """SQL execution errors."""
    pass

