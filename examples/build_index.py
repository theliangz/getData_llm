#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Example script for building vector indexes.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.service import SchemaIndexService
from src.utils import setup_logging

# Setup logging
setup_logging()

if __name__ == "__main__":
    # Example SQL pairs (you can load from file or database)
    sql_pairs = [
        {
            "question": "查询所有用户",
            "sql": "SELECT * FROM users"
        },
        {
            "question": "查询最近一周的订单数量",
            "sql": "SELECT COUNT(*) FROM orders WHERE order_date >= today() - 7"
        },
        # Add more examples as needed
    ]
    
    # Create index service
    index_service = SchemaIndexService()
    
    try:
        # Build indexes
        print("Building indexes...")
        index_service.build_indexes(sql_pairs=sql_pairs)
        print("Indexes built successfully!")
    except Exception as e:
        print(f"Error building indexes: {e}")
        sys.exit(1)
    finally:
        index_service.close()

