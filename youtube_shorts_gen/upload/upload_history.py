"""Module for tracking YouTube upload history to prevent duplicate uploads."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class UploadHistory:
    """Tracks YouTube upload history to prevent duplicate uploads."""

    def __init__(self, history_file: str | None = None):
        """Initialize the upload history tracker.

        Args:
            history_file: Path to the history JSON file (optional)
        """
        if history_file is None:
            # Default to a file in the same directory as this module
            module_dir = Path(__file__).parent
            history_file = str(module_dir / "upload_history.json")

        self.history_file = Path(history_file)
        self._ensure_history_file()

    def _ensure_history_file(self) -> None:
        """Ensure the history file exists, creating it if necessary."""
        if not self.history_file.exists():
            # Create an empty history file
            self.history_file.write_text(
                json.dumps({"uploads": []}, indent=2), encoding="utf-8"
            )
            logging.info("Created new upload history file: %s", self.history_file)

    def load_history(self) -> dict[str, list[dict[str, Any]]]:
        """Load the upload history from the JSON file.

        Returns:
            Dictionary containing upload history
        """
        try:
            return json.loads(self.history_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.warning("Error loading history file, creating new one: %s", e)
            empty_history = {"uploads": []}
            self.history_file.write_text(
                json.dumps(empty_history, indent=2), encoding="utf-8"
            )
            return empty_history

    def save_history(self, history: dict[str, list[dict[str, Any]]]) -> None:
        """Save the upload history to the JSON file.

        Args:
            history: Dictionary containing upload history
        """
        self.history_file.write_text(json.dumps(history, indent=2), encoding="utf-8")

    def is_duplicate_title(self, title: str) -> bool:
        """Check if a title has been uploaded before.

        Args:
            title: Video title to check

        Returns:
            True if the title has been uploaded before, False otherwise
        """
        history = self.load_history()

        # Check if the title exists in the history using any() expression
        return any(upload["title"] == title for upload in history["uploads"])

    def add_upload(self, title: str, video_url: str, story_content: str) -> None:
        """Add a new upload to the history.

        Args:
            title: Title of the uploaded video
            video_url: URL of the uploaded video
            story_content: Content of the story used for the video
        """
        history = self.load_history()

        # Add the new upload
        history["uploads"].append(
            {
                "title": title,
                "url": video_url,
                "story_snippet": story_content[:100] + "..."
                if len(story_content) > 100
                else story_content,
                "upload_date": datetime.now().isoformat(),
            }
        )

        # Save the updated history
        self.save_history(history)
        logging.info("Added upload to history: %s", title)

    def get_recent_uploads(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the most recent uploads.

        Args:
            limit: Maximum number of uploads to return

        Returns:
            List of recent uploads
        """
        history = self.load_history()

        # Sort by upload date (newest first) and limit
        sorted_uploads = sorted(
            history["uploads"], key=lambda x: x.get("upload_date", ""), reverse=True
        )

        return sorted_uploads[:limit]
