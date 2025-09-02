import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

journal_handler: logging.Handler | None = None
try:
    from systemd.journal import JournalHandler  # pyright: ignore[reportMissingImports]

    journal_handler = JournalHandler()
    journal_handler.setLevel(logging.INFO)  # pyright: ignore[reportOptionalMemberAccess]
    journal_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))  # pyright: ignore[reportOptionalMemberAccess]
except ImportError:
    pass

file_handler: logging.Handler | None = None
if os.path.exists("/home/solvrocam/"):
    if not os.path.isdir("/home/solvrocam/hardware-solvro-bot-office-cam/logs"):
        os.mkdir("/home/solvrocam/hardware-solvro-bot-office-cam/logs")

    file_handler = TimedRotatingFileHandler(
        "/home/solvrocam/hardware-solvro-bot-office-cam/logs/log",
        when="D",
        backupCount=7,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )


# Configure logging
def setup_logging(logger: logging.Logger) -> None:
    logger.propagate = False
    level = os.getenv("LOG_LEVEL", "DEBUG").upper()
    logger.setLevel(level=getattr(logging, level, logging.DEBUG))
    logger.addHandler(logging.StreamHandler(sys.stderr))

    if journal_handler is not None:
        logger.addHandler(journal_handler)
    if file_handler is not None:
        logger.addHandler(file_handler)
