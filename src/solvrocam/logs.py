import logging
import os
from logging.handlers import TimedRotatingFileHandler

from systemd.journal import JournalHandler  # pyright: ignore[reportMissingImports]

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

journal_handler = JournalHandler()
journal_handler.setLevel(logging.INFO)
journal_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))


# Configure logging
def setup_logging(logger: logging.Logger) -> None:
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    logger.addHandler(file_handler)
    logger.addHandler(journal_handler)
