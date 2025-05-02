# youtube_script_gen.py

import base64
import os

from dotenv import load_dotenv
from openai import OpenAI


def generate_story_and_image(run_dir: str):
    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )

    prompt = """
    You are a short-form story writer.
    Write a captivating, extremely short story (3 sentences max) for a general audience,
    suitable for a YouTube Short or TikTok.
    Avoid numbering the sentences. Just write the story naturally.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=300
    )

    # Safely extract story content with null checks
    story = ""
    if response and response.choices and len(response.choices) > 0:
        if response.choices[0].message and response.choices[0].message.content:
            story = response.choices[0].message.content.strip()
    
    prompt_path = os.path.join(run_dir, "story_prompt.txt")
    with open(prompt_path, "w") as f:
        f.write(story)
    print(f"Saved story: {prompt_path}")

    image_prompt = (
        f"Create a single surreal, symbolic image that represents this story: "
        f"\"{story}\" Do not include any text; focus purely on visual storytelling."
    )

    result = client.images.generate(
        model="gpt-image-1",
        prompt=image_prompt,
        size="1024x1024",
        n=1
    )

    image_path = os.path.join(run_dir, "story_image.png")
    # Safely extract and decode image data with null checks
    with open(image_path, "wb") as f:
        if result and result.data and len(result.data) > 0 and result.data[0].b64_json:
            f.write(base64.b64decode(result.data[0].b64_json))
        else:
            # Write an empty image if no data is available
            f.write(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            ))

    print(f"Saved image: {image_path}")
