"""Scraper for Dogdrip website content."""

import logging
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from youtube_shorts_gen.scrapers.base_scraper import ContentScraper


class DogdripScraper(ContentScraper):
    """Scraper for fetching short stories and content from Dogdrip website."""

    def __init__(
        self,
        url: str = "https://www.dogdrip.net/doc/category/18567755?sort_index=popular",
    ):
        """Initialize the Dogdrip scraper.

        Args:
            url: URL to the Dogdrip content category
        """
        self.url = url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def _extract_post_links(self, soup: BeautifulSoup) -> list[tuple[str, str]]:
        """Extract post links and titles from the listing page.

        Args:
            soup: BeautifulSoup object of the listing page

        Returns:
            List of (url, title) tuples limited to 5 unique items
        """
        post_items = []
        for a in soup.select("td.title a.link-reset[data-document-srl]"):
            href = a.get("href")
            if not href or "/doc/" not in href:
                continue
            full_url = urljoin(self.url, href)
            title_span = a.select_one("span.ed.title-link")
            title_text = title_span.get_text(strip=True) if title_span else ""
            post_items.append((full_url, title_text))

        # Deduplicate and limit to 5
        seen_urls = set()
        post_items_unique = []
        for link_url, title_text in post_items:
            if link_url not in seen_urls:
                seen_urls.add(link_url)
                post_items_unique.append((link_url, title_text))

        return post_items_unique[:5]

    def _extract_post_content(self, link: str, title: str) -> str | None:
        """Extract content from a single post.

        Args:
            link: URL of the post
            title: Title of the post

        Returns:
            Formatted story text or None if extraction failed
        """
        try:
            time.sleep(1)  # Respectful scraping
            post_resp = requests.get(link, headers=self.headers, timeout=10)
            post_resp.raise_for_status()
            post_soup = BeautifulSoup(post_resp.text, "html.parser")

            # Extract document ID from URL path
            doc_id = urlparse(link).path.split("/")[-1]
            content_elem = post_soup.select_one(f"div.document_{doc_id}_0")

            if not content_elem:
                content_elem = post_soup.select_one("div.xe_content")

            if not content_elem:
                logging.warning("Failed to extract content from %s", link)
                return None

            content = content_elem.get_text(separator=" ", strip=True)
            content = re.sub(r"\s+", " ", content)

            if len(content) > 500:
                content = content[:500] + "..."

            full_story = f"{title}. {content}"
            logging.info("Fetched story from Dogdrip: %s", title)
            return full_story

        except requests.RequestException as e:
            logging.warning("Network error fetching post %s: %s", link, e)
        except ValueError as e:
            logging.warning("Value error processing post %s: %s", link, e)
        except Exception as e:
            logging.warning("Unexpected error fetching post %s: %s", link, e)

        return None

    def fetch_content(self) -> list[str]:
        """Fetch content from Dogdrip website.

        Returns:
            List of story texts
        """
        stories = []

        try:
            # Fetch the main page that lists posts
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            post_items = self._extract_post_links(soup)

            # Visit each post to extract content
            for link, title in post_items:
                story_text = self._extract_post_content(link, title)
                if story_text:
                    stories.append(story_text)

            logging.info("Fetched %d Dogdrip stories", len(stories))
            return stories

        except requests.RequestException as e:
            logging.warning("Network error fetching from Dogdrip: %s", e)
        except ValueError as e:
            logging.warning("Value error processing Dogdrip data: %s", e)
        except Exception as e:
            logging.warning("Unexpected error fetching from Dogdrip: %s", e)

        return []
