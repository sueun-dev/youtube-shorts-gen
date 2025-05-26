"""Module for fetching content from the internet for YouTube shorts."""

import base64
import logging
import random
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from youtube_shorts_gen.utils.config import (
    IMAGE_PROMPT_TEMPLATE,
    OPENAI_CHAT_MODEL,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_SIZE,
)
from youtube_shorts_gen.utils.openai_client import get_openai_client


class InternetContentFetcher:
    """Fetches content from the internet, processes it with OpenAI, and generates images."""

    def __init__(self, run_dir: str):
        """Initialize the internet content fetcher.

        Args:
            run_dir: Directory to save fetched content
        """
        self.run_dir = Path(run_dir)
        self.prompt_path = self.run_dir / "story_prompt.txt"
        self.client = get_openai_client()

        # Create images directory
        self.images_dir = self.run_dir / "images"
        self.images_dir.mkdir(exist_ok=True)

        # Website URLs to fetch content from
        self.websites = [
            "https://gall.dcinside.com/board/lists/?id=dcbest",  # DCInside 베스트 갤러리
            "https://gall.dcinside.com/board/lists/?id=hit",  # DCInside 힛갤러리
            "https://gall.dcinside.com/board/lists/?id=issuezoom",  # DCInside 이슈줌
        ]

        # Mapping file for paragraphs and images
        self.mapping_path = self.run_dir / "paragraph_image_mapping.txt"

    def _fetch_popular_posts(self, website_url: str, limit: int = 5) -> list:
        """Fetch popular post URLs from a website.

        Args:
            website_url: URL of the website to fetch from
            limit: Maximum number of posts to fetch

        Returns:
            List of post URLs
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }

        try:
            response = requests.get(website_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Find posts with high view counts or recommended counts
            post_links = []
            # Typical DCInside post row class
            post_rows = soup.select(".gall_list .us-post")

            for row in post_rows[: limit * 2]:  # Get more than needed to filter
                try:
                    # Check if it has high view count or recommendations
                    view_count = int(row.select_one(".gall_count").text.strip())
                    recommend_count = int(
                        row.select_one(".gall_recommend").text.strip()
                    )

                    # Threshold for popularity
                    if view_count > 1000 or recommend_count > 10:
                        link_element = row.select_one(".gall_tit a")
                        if link_element and "href" in link_element.attrs:
                            post_url = (
                                "https://gall.dcinside.com" + link_element["href"]
                            )
                            post_links.append(post_url)
                except (AttributeError, ValueError):
                    continue

            # Limit the number of posts
            return post_links[:limit]

        except (requests.RequestException, ValueError) as e:
            logging.warning("Error fetching from website: %s", e)
            return []

    def _fetch_post_content(self, post_url: str) -> str:
        """Fetch the content of a post.

        Args:
            post_url: URL of the post to fetch

        Returns:
            Post content as text
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }

        try:
            response = requests.get(post_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Get post title
            title_element = soup.select_one(".title_subject")
            title = title_element.text.strip() if title_element else "Untitled Post"

            # Get post content
            content_element = soup.select_one(".writing_view_box")
            content = content_element.text.strip() if content_element else ""

            # Combine title and content
            full_content = f"{title}\n\n{content}"

            # Clean up the content (remove excessive whitespace, etc.)
            return re.sub(r"\s+", " ", full_content).strip()

        except (requests.RequestException, ValueError) as e:
            logging.warning("Error fetching post content: %s", e)
            return ""

    def _summarize_and_split_content(self, content: str) -> list:
        """Summarize and split content into paragraphs using OpenAI.

        Args:
            content: The content to summarize and split

        Returns:
            List of paragraphs
        """
        if not content:
            return []

        # Truncate content if it's too long
        if len(content) > 4000:
            content = content[:4000] + "..."

        prompt = f"""
        다음 인터넷 게시글을 요약하고 4-6개의 단락으로 나누어 주세요. 
        각 단락은 짧고 명확해야 하며, 유튜브 쇼츠에 적합한 내용이어야 합니다.
        각 단락은 독립적으로 이해될 수 있어야 하며, 전체적으로 스토리가 이어져야 합니다.
        단락은 줄바꿈으로 구분해 주세요.
        
        게시글:
        {content}
        """

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000,
            )

            # Validate API response
            if not response.choices or not response.choices[0].message:
                raise ValueError("OpenAI API returned empty response")

            summarized_content = response.choices[0].message.content
            if not summarized_content:
                raise ValueError("OpenAI API returned empty content")

            # Split into paragraphs
            paragraphs = [
                p.strip() for p in summarized_content.split("\n") if p.strip()
            ]

            # Filter out very short paragraphs and limit to a reasonable number
            paragraphs = [p for p in paragraphs if len(p) > 20]
            if len(paragraphs) > 6:
                paragraphs = paragraphs[:6]

            return paragraphs

        except Exception as e:
            logging.error("Error summarizing content with OpenAI: %s", e)

            # Fallback: simple paragraph splitting
            simple_paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            if len(simple_paragraphs) > 6:
                simple_paragraphs = simple_paragraphs[:6]
            return simple_paragraphs

    def _generate_image_for_paragraph(self, paragraph: str, index: int) -> str:
        """Generate an image for a paragraph using DALL·E.

        Args:
            paragraph: The paragraph to illustrate
            index: The paragraph index (for filename)

        Returns:
            Path to the generated image
        """
        # Create a prompt for the image based on the paragraph
        image_prompt = IMAGE_PROMPT_TEMPLATE.format(story=paragraph)

        try:
            result = self.client.images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=image_prompt,
                size=OPENAI_IMAGE_SIZE,
                quality="low",
                n=1,
            )

            # Validate API response
            if not result.data or not result.data[0].b64_json:
                raise ValueError(
                    "OpenAI API returned empty response for image generation"
                )

            image_data = result.data[0].b64_json

            # Save image to file
            image_path = self.images_dir / f"paragraph_{index+1}.png"
            with open(image_path, "wb") as f:
                f.write(base64.b64decode(image_data))

            logging.info("Generated image for paragraph %d: %s", index + 1, image_path)
            return str(image_path)

        except Exception as e:
            logging.error("Error generating image for paragraph %d: %s", index + 1, e)
            return ""

    def run(self) -> dict:
        """Fetch content from the internet, process it, and generate images.

        Returns:
            Dictionary with story text, paragraphs, and image paths
        """
        all_posts = []

        # Try each website
        for website_url in self.websites:
            post_urls = self._fetch_popular_posts(website_url)

            for post_url in post_urls:
                content = self._fetch_post_content(post_url)
                if content:
                    all_posts.append(content)

        if not all_posts:
            # Fallback if no posts found
            story = (
                "인터넷에서 재미있는 글을 찾지 못했습니다. 대신 이 이야기를 "
                "사용합니다. 어느 날 한 유저가 게시판에 기묘한 경험을 올렸습니다. "
                "그의 컴퓨터가 갑자기 혼자서 글을 쓰기 시작했다고 합니다. 처음에는 "
                "장난으로 생각했지만, 점점 더 이상한 일이 일어났습니다. 결국 그것은 "
                "인공지능이 만든 이야기였다는 것이 밝혀졌습니다."
            )
            paragraphs = [
                "인터넷에서 재미있는 글을 찾지 못했습니다. 대신 이 이야기를 "
                "사용합니다.",
                "어느 날 한 유저가 게시판에 기묘한 경험을 올렸습니다. 그의 컴퓨터가 "
                "갑자기 혼자서 글을 쓰기 시작했다고 합니다.",
                "처음에는 장난으로 생각했지만, 점점 더 이상한 일이 일어났습니다.",
                "결국 그것은 인공지능이 만든 이야기였다는 것이 밝혀졌습니다.",
            ]
        else:
            # Select a random post
            selected_post = random.choice(all_posts)

            # Summarize and split into paragraphs
            paragraphs = self._summarize_and_split_content(selected_post)

            # Combine paragraphs into a single story
            story = " ".join(paragraphs)

        # Save complete story to file
        self.prompt_path.write_text(story, encoding="utf-8")
        logging.info("Saved internet story: %s", self.prompt_path)

        # Generate an image for each paragraph
        image_paths = []
        for i, paragraph in enumerate(paragraphs):
            image_path = self._generate_image_for_paragraph(paragraph, i)
            if image_path:
                image_paths.append(image_path)

        # Create a mapping file between paragraphs and images
        with open(self.mapping_path, "w", encoding="utf-8") as f:
            f.write(f"Story: {story}\n\n")
            for i, (paragraph, image) in enumerate(
                zip(paragraphs, image_paths, strict=False)
            ):
                f.write(f"Paragraph {i+1}: {paragraph}\nImage: {image}\n\n")

        return {"story": story, "paragraphs": paragraphs, "image_paths": image_paths}
