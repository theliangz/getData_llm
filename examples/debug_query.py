#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Debug script to test database queries and verify data.
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
        db_client = DatabaseClient()
        
        # Test queries to debug the issue
        test_queries = [
            # 1. Simple count to verify table has data
            ("SELECT COUNT(*) FROM \"acdmhfe\".\"goms_flight\"", "Total flights count"),
            
            # 2. Check if there's any data in October 2025
            ("SELECT COUNT(*) FROM \"acdmhfe\".\"goms_flight\" WHERE \"fdate\" >= 20251001 AND \"fdate\" <= 20251031", "October 2025 flights"),
            
            # 3. Check if there's any MU airline data
            ("SELECT COUNT(*) FROM \"acdmhfe\".\"goms_flight\" WHERE \"airlines_iata\" = 'MU'", "MU airline flights"),
            
            # 4. Check the actual query
            ("SELECT COUNT(*) FROM \"acdmhfe\".\"goms_flight\" WHERE \"airlines_iata\" = 'MU' AND \"fdate\" >= 20251001 AND \"fdate\" <= 20251031", "MU flights in October 2025"),
            
            # 5. Check fdate format - sample some dates
            ("SELECT \"fdate\", COUNT(*) as cnt FROM \"acdmhfe\".\"goms_flight\" WHERE \"airlines_iata\" = 'MU' GROUP BY \"fdate\" ORDER BY \"fdate\" DESC LIMIT 10", "Sample MU flight dates"),
            
            # 6. Check if fdate needs conversion
            ("SELECT toTypeName(\"fdate\") as fdate_type FROM \"acdmhfe\".\"goms_flight\" LIMIT 1", "fdate column type"),
            
            # 7. Try with correct Unix timestamp conversion
            ("SELECT COUNT(*) FROM \"acdmhfe\".\"goms_flight\" WHERE \"airlines_iata\" = 'MU' AND toDate(toDateTime(\"fdate\")) >= '2025-10-01' AND toDate(toDateTime(\"fdate\")) <= '2025-10-31'", "MU flights with correct Unix timestamp conversion"),
            
            # 8. Verify the conversion works - show some sample dates
            ("SELECT toDate(toDateTime(\"fdate\")) as flight_date, COUNT(*) as cnt FROM \"acdmhfe\".\"goms_flight\" WHERE \"airlines_iata\" = 'MU' GROUP BY flight_date ORDER BY flight_date DESC LIMIT 10", "Sample MU flight dates (converted)"),
        ]
        
        print("=" * 80)
        print("Database Query Debug Tool")
        print("=" * 80)
        
        for sql, description in test_queries:
            print(f"\n[Test] {description}")
            print(f"SQL: {sql}")
            try:
                result = db_client.execute(sql)
                print(f"Result: {result}")
                if result:
                    print(f"First row: {result[0]}")
                    print(f"Result type: {type(result[0])}")
                    if isinstance(result[0], (list, tuple)):
                        print(f"First row values: {result[0]}")
            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()
            print("-" * 80)
        
        db_client.close()
        print("\nDebug completed!")
        
    except Exception as e:
        logger.error(f"Debug script failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

