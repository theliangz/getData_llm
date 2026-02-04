#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Example script for querying with NL2SQL.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.service import QueryService
from src.utils import setup_logging

# Setup logging
setup_logging()

if __name__ == "__main__":
    # Create query service
    query_service = QueryService()
    
    try:
        # Example questions
        questions = [
            "查询全国所有双机场代码",
            "查询2025年11月份全国航班总量",
            # Add more questions as needed
        ]
        
        for question in questions:
            print(f"\n{'='*60}")
            print(f"Question: {question}")
            print(f"{'='*60}")
            
            try:
                result = query_service.text2sql(question)
                
                print(f"\nReasoning:\n{result['reasoning']}")
                print(f"\nFinal SQL:\n{result['final_sql']}")
                print(f"\nDiagnosis: {result['diagnosis']}")
                
                if result['diagnosis']['success']:
                    print(f"\nResults ({len(result['data_result'])} rows):")
                    # Print first 5 rows
                    for i, row in enumerate(result['data_result'][:5], 1):
                        print(f"  {i}. {row}")
                    if len(result['data_result']) > 5:
                        print(f"  ... and {len(result['data_result']) - 5} more rows")
                else:
                    print(f"\nQuery failed: {result['diagnosis']['message']}")
            except Exception as e:
                print(f"Error processing question: {e}")
    finally:
        query_service.close()

