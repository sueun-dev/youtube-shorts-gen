import base64
import logging
import os

from openai import OpenAI

from youtube_shorts_gen.config import (
    IMAGE_PROMPT_TEMPLATE,
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_SIZE,
    get_story_prompt,
)


class YouTubeScriptGenerator:
    def __init__(self, run_dir: str, temperature: float = 0.9, max_tokens: int = 300):
        self.run_dir = run_dir
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.prompt_path = os.path.join(run_dir, "story_prompt.txt")
        self.image_path = os.path.join(run_dir, "story_image.png")
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate_story(self) -> str:
        """Generate a story from OpenAI chat model and save to file."""
        response = self.client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[{"role": "user", "content": get_story_prompt()}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        
        # None 체크 및 오류 처리
        if not response.choices:
            raise ValueError("OpenAI API returned empty choices list")
            
        if not response.choices[0].message:
            raise ValueError("OpenAI API returned empty message")
            
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI API returned empty content")
            
        # content가 None이 아님을 보장했으므로 strip() 호출 안전
        story = content.strip()

        with open(self.prompt_path, "w", encoding="utf-8") as f:
            f.write(story)

        logging.info("Saved story: %s", self.prompt_path)
        return story

    def generate_image(self, story: str) -> None:
        """Generate an image from the story using DALL·E and save to file."""
        image_prompt = IMAGE_PROMPT_TEMPLATE.format(story=story)

        result = self.client.images.generate(
            model=OPENAI_IMAGE_MODEL,
            prompt=image_prompt,
            size=OPENAI_IMAGE_SIZE,
            n=1,
        )
        
        # None 체크 및 오류 처리
        if not result.data or not result.data[0].b64_json:
            raise ValueError("OpenAI API returned empty response for image generation")
            
        image_data = result.data[0].b64_json

        with open(self.image_path, "wb") as f:
            f.write(base64.b64decode(image_data))

        logging.info("Saved image: %s", self.image_path)

    def run(self):
        """Generate story and image together."""
        story = self.generate_story()
        self.generate_image(story)
