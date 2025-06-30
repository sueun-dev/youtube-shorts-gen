import logging
import re
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi

from youtube_shorts_gen.scrapers.base_scraper import ContentScraper


class YouTubeTranscriptScraper(ContentScraper):
    """Extracts transcript text from YouTube videos."""

    def __init__(self) -> None:
        """Initializes the YouTubeTranscriptScraper."""
        self.youtube_url = ""
        self.transcript_api = YouTubeTranscriptApi()

    def fetch_content(self, youtube_url: str) -> str | None:
        """Returns the full transcript or ``None`` if unavailable."""
        return self.fetch_transcript(youtube_url)

    def fetch_transcript(self, youtube_url: str) -> str | None:
        """Fetches and combines all transcript segments for a YouTube video."""
        video_id = self._prepare_video_id(youtube_url)
        if not video_id:
            return None
        return self._try_auto_generated_captions(video_id)

    def _prepare_video_id(self, youtube_url: str) -> str | None:
        """Extracts and cleans the video ID from a YouTube URL."""
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            logging.error("Could not extract video ID from URL: %s", youtube_url)
            return None
        if "&" in video_id:
            video_id = video_id.split("&")[0]
        logging.info("Extracted video ID: %s", video_id)
        return video_id

    def _try_auto_generated_captions(self, video_id: str) -> str | None:
        """Attempts to fetch auto-generated captions without `partial`/`lambda`."""
        logging.info("Trying to fetch transcript using auto-generated captions")
        fetched_transcript = self._try_auto_captions(video_id)

        if hasattr(fetched_transcript, "snippets") and fetched_transcript.snippets:
            full_transcript = " ".join(
                snippet.text for snippet in fetched_transcript.snippets
            )
            logging.info("Successfully fetched transcript via auto-generated captions")
            return full_transcript

        if isinstance(fetched_transcript, list) and fetched_transcript:
            full_transcript = " ".join(
                segment["text"] for segment in fetched_transcript
            )
            logging.info("Successfully fetched transcript via auto-generated captions")
            return full_transcript

        logging.info("Auto-generated caption fetch returned empty transcript list")
        return None

    def _is_non_empty(self, obj: Any) -> bool:
        """Checks whether a transcript object actually contains captions."""
        if not obj:
            return False
        if hasattr(obj, "snippets"):
            return bool(obj.snippets)
        if hasattr(obj, "__len__"):
            return len(obj) > 0
        return True

    def _try_auto_captions(self, video_id: str):
        """
        Prefers auto-generated captions; otherwise returns first non-empty transcript.
        """
        transcripts = list(self.transcript_api.list(video_id))
        logging.info("Found %d transcript(s) for auto-caption check", len(transcripts))

        for prefer_generated in (True, False):
            for transcript in transcripts:
                if transcript.is_generated is prefer_generated:
                    result = transcript.fetch()
                    if self._is_non_empty(result):
                        return result
        return []

    def extract_video_id(self, youtube_url: str) -> str | None:
        """Extracts the 11-character video ID from a YouTube URL."""
        patterns = [
            (
                r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|"
                r"youtube\.com\/v\/|youtube\.com\/e\/|youtube\.com\/user\/\S+\/\S+\/|"
                r"youtube\.com\/\S+\/\S+\/\S+|youtube\.com\/watch\?.*v=|"
                r"youtube\.com\/\S+\/\S+\/|youtube\.com\/shorts\/)"
                r"([^\"&?\/\s]{11})"
            ),
            r"youtube\.com\/watch\?time_continue=\d+&v=([^\"&?\/\s]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        return None
