"""
Centralized logging configuration.

Functions:
- get_logger(name): Create logger with consistent format

See ARCHITECTURE.md for usage details.
"""

import logging
import sys
from tqdm import tqdm


class TqdmLoggingHandler(logging.Handler):
    """Logging handler that writes through tqdm to keep progress bars at bottom."""

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
        except Exception:
            self.handleError(record)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get or create a configured logger that works with tqdm progress bars.

    Args:
        name: Logger name (typically __name__ of the module)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(level)

        # Use TqdmLoggingHandler to keep progress bars at bottom
        console_handler = TqdmLoggingHandler()
        console_handler.setLevel(level)

        # Format: timestamp - name - level - message
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger


def configure_logging(level: str = "INFO"):
    """
    Configure root logger with specified level.

    Args:
        level: Log level as string ("DEBUG", "INFO", "WARNING", "ERROR")
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )
