#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Logging utilities.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from config import get_settings


def setup_logging(log_dir: Optional[str] = None, log_level: Optional[str] = None) -> None:
    """Setup logging configuration."""
    settings = get_settings()
    log_dir = Path(log_dir or settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_level = log_level or settings.log_level
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # File handler (daily log file)
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"nl2sql_{date_str}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)

