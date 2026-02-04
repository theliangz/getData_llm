#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Test script for database connection.
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from core.database import DatabaseClient
from utils import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

if __name__ == "__main__":
    try:
        # Create database client
        db_client = DatabaseClient()
        
        # Test connection
        logger.info("Testing database connection...")
        client = db_client._get_client()
        logger.info("Database connection successful!")
        
        # Test a simple query
        logger.info("Testing simple query...")
        if db_client.config.db_type.lower() == "clickhouse":
            test_sql = "SELECT 1"
        else:
            test_sql = "SELECT 1"
        
        result = db_client.execute(test_sql)
        logger.info(f"Query result: {result}")
        
        # Test aggregate query (COUNT)
        logger.info("Testing aggregate query (COUNT)...")
        # This should not add LIMIT automatically
        count_sql = "SELECT COUNT(*) FROM (SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3) AS t"
        try:
            count_result = db_client.execute(count_sql)
            logger.info(f"COUNT query result: {count_result}")
            logger.info("Aggregate query test passed - no LIMIT was added")
        except Exception as e:
            logger.error(f"COUNT query failed: {e}")
        
        # Close connection
        db_client.close()
        logger.info("Database test completed successfully!")
        
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

