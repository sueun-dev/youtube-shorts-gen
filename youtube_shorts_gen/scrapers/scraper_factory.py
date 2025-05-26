"""Factory for creating content scrapers."""


from youtube_shorts_gen.scrapers.base_scraper import ContentScraper
from youtube_shorts_gen.scrapers.dogdrip_scraper import DogdripScraper


class ScraperFactory:
    """Factory class for creating appropriate content scrapers."""

    _scrapers: dict[str, type[ContentScraper]] = {"dogdrip": DogdripScraper}

    @classmethod
    def get_scraper(cls, source_type: str) -> ContentScraper:
        """Get the appropriate scraper for the given source type.

        Args:
            source_type: Type of content source to scrape

        Returns:
            A content scraper instance

        Raises:
            ValueError: If the source type is not supported
        """
        scraper_class = cls._scrapers.get(source_type.lower())
        if not scraper_class:
            raise ValueError(
                "Unsupported source type: {}. Supported types: {}".format(
                    source_type, ", ".join(cls._scrapers.keys())
                )
            )

        return scraper_class()
