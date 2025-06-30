import logging
from datetime import datetime
from pathlib import Path

from youtube_shorts_gen.utils.config import RUNS_BASE_DIR


def setup_logging() -> None:
    """Configure logging for the application.

    Sets up basic logging configuration with timestamp formatting.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def setup_run_directory() -> Path:
    """Create and return a timestamped directory for the current run."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = Path(RUNS_BASE_DIR) / timestamp
    run_dir.mkdir(parents=True)
    logging.info("[SETUP] Created run directory: %s. Ready to go!", run_dir)
    return run_dir
