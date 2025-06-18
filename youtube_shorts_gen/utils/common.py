import logging
import os


def ensure_directory_exists(directory_path):
    """
    Ensures that a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory to ensure exists
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
    except Exception as e:
        logging.error(f"Error creating directory {directory_path}: {e}")
        raise
