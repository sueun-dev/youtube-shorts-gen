"""Base interface for web content scrapers."""

from abc import ABC, abstractmethod


class ContentScraper(ABC):
    """Abstract base class for content scrapers."""

    @abstractmethod
    def fetch_content(self) -> list[str]:
        """Fetch content from the source.

        Returns:
            List of story texts or content snippets
        """
        pass
