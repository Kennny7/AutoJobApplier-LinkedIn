"""
Logger configuration using Python's logging module and Rich.
Provides a single `get_logger` function that returns a logger with both file and console handlers.
"""

import logging
import os
from pathlib import Path
from rich.logging import RichHandler

def get_logger(name: str = "AutoApply", log_dir: str = "data/logs") -> logging.Logger:
    """
    Creates and returns a logger with Rich console output and rotating file handler.
    
    Args:
        name: Logger name.
        log_dir: Directory for log files.
    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    # Avoid duplicate handlers if already set up
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler with Rich formatting
    console_handler = RichHandler(rich_tracebacks=True, markup=True)
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)

    # File handler - detailed logs
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        os.path.join(log_dir, "applier.log"), encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger