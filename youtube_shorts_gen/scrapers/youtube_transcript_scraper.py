"""Extract transcript text from YouTube videos via youtube-transcript-api."""

import logging
import re
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi

# Patterns that capture the 11-character video ID from common YouTube URL shapes.
_VIDEO_ID_PATTERNS: tuple[str, ...] = (
    (
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|"
        r"youtube\.com/v/|youtube\.com/e/|youtube\.com/shorts/)"
        r"([^\"&?/\s]{11})"
    ),
    r"youtube\.com/watch\?time_continue=\d+&v=([^\"&?/\s]{11})",
)


class YouTubeTranscriptScraper:
    """Fetches and concatenates the transcript of a YouTube video."""

    def __init__(self) -> None:
        self.transcript_api = YouTubeTranscriptApi()

    def fetch_transcript(self, youtube_url: str) -> str | None:
        """Return the full transcript text, or ``None`` if unavailable."""
        video_id = self._prepare_video_id(youtube_url)
        if not video_id:
            return None
        return self._fetch_captions(video_id)

    def extract_video_id(self, youtube_url: str) -> str | None:
        """Extract the 11-character video ID from a YouTube URL."""
        for pattern in _VIDEO_ID_PATTERNS:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        return None

    def _prepare_video_id(self, youtube_url: str) -> str | None:
        """Extract and normalise the video ID from a URL."""
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            logging.error("Could not extract video ID from URL: %s", youtube_url)
            return None
        # Strip any trailing query parameters that slipped into the captured ID.
        video_id = video_id.split("&", 1)[0]
        logging.info("Extracted video ID: %s", video_id)
        return video_id

    def _fetch_captions(self, video_id: str) -> str | None:
        """Fetch the first non-empty transcript, preferring auto-generated captions."""
        transcript = self._select_transcript(video_id)
        snippets = getattr(transcript, "snippets", None)
        if snippets:
            text = " ".join(snippet.text for snippet in snippets)
            logging.info("Successfully fetched transcript for %s", video_id)
            return text
        # Fall back to the legacy list-of-dicts shape from older API versions.
        if isinstance(transcript, list) and transcript:
            text = " ".join(segment["text"] for segment in transcript)
            logging.info("Successfully fetched transcript for %s", video_id)
            return text
        logging.info("No captions available for %s", video_id)
        return None

    def _select_transcript(self, video_id: str) -> Any:
        """Return the first non-empty transcript, preferring auto-generated ones."""
        transcripts = list(self.transcript_api.list(video_id))
        logging.info("Found %d transcript(s) for %s", len(transcripts), video_id)
        for prefer_generated in (True, False):
            for transcript in transcripts:
                if transcript.is_generated is prefer_generated:
                    fetched = transcript.fetch()
                    if self._is_non_empty(fetched):
                        return fetched
        return None

    @staticmethod
    def _is_non_empty(obj: Any) -> bool:
        """Return ``True`` if the fetched transcript actually contains captions."""
        if not obj:
            return False
        snippets = getattr(obj, "snippets", None)
        if snippets is not None:
            return bool(snippets)
        if hasattr(obj, "__len__"):
            return len(obj) > 0
        return True
