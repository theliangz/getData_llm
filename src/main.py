#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Main application entry point.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path to support both direct execution and module import
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router
from utils import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NL2SQL Service",
    description="Natural Language to SQL service using LLM and vector retrieval",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("NL2SQL service starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("NL2SQL service shutting down...")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

