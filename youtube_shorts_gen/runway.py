# runway.py

import base64
import os
import time

import requests
from dotenv import load_dotenv
from runwayml import RunwayML


def load_api_key(env_var="RUNWAY_API_KEY"):
    load_dotenv()
    key = os.getenv(env_var)
    if not key:
        raise RuntimeError(f"{env_var} not found")
    os.environ["RUNWAYML_API_SECRET"] = key
    return key

def image_to_data_uri(path: str) -> str:
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"

def generate_video(run_dir: str):
    load_api_key()
    client = RunwayML()

    image_path = os.path.join(run_dir, "story_image.png")
    prompt_path = os.path.join(run_dir, "story_prompt.txt")
    with open(prompt_path) as f:
        prompt_text = f.read().strip()

    prompt_image = image_to_data_uri(image_path)

    response = client.image_to_video.create(
        model="gen3a_turbo",
        prompt_image=prompt_image,
        prompt_text=prompt_text,
        ratio="768:1280"
    )
    task_id = response.id
    print(f"Task submitted (ID: {task_id})")

    time.sleep(10)
    task = client.tasks.retrieve(task_id)
    while task.status not in ["SUCCEEDED", "FAILED"]:
        print(f"Status: {task.status}")
        time.sleep(10)
        task = client.tasks.retrieve(task_id)

    if task.status == "SUCCEEDED" and task.output:
        video_url = task.output[0]
        output_path = os.path.join(run_dir, "output_story_video.mp4")
        r = requests.get(video_url, stream=True)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            print(f"Downloaded video: {output_path}")
        else:
            print("Failed to download video.")
    else:
        print(f"Task failed: {task.status}")
