import base64
import logging
import os
import time

import requests
from runwayml import RunwayML

from youtube_shorts_gen.config import RUNWAY_API_KEY


class VideoGenerator:
    """RunwayML을 사용하여 이미지 기반 영상 생성기."""

    def __init__(self, run_dir: str):
        """
        Args:
            run_dir (str): 생성된 이미지 및 텍스트 프롬프트가 위치한 디렉터리
        """
        self.run_dir = run_dir
        if RUNWAY_API_KEY is None:
            raise ValueError("RUNWAY_API_KEY is not set in environment variables")
        os.environ["RUNWAYML_API_SECRET"] = RUNWAY_API_KEY
        self.client = RunwayML()

    def _image_to_data_uri(self, image_path: str) -> str:
        """이미지를 base64로 인코딩하여 data URI로 변환"""
        ext = os.path.splitext(image_path)[1][1:].lower()
        mime = f"image/{'jpeg' if ext == 'jpg' else ext}"

        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime};base64,{encoded}"

    def generate(self) -> None:
        """RunwayML에 요청을 보내 이미지와 프롬프트로부터 영상을 생성한다.
        완료 후 영상 파일을 run_dir에 저장한다.
        """
        image_path = os.path.join(self.run_dir, "story_image.png")
        prompt_path = os.path.join(self.run_dir, "story_prompt.txt")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"이미지 파일이 없습니다: {image_path}")
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"프롬프트 파일이 없습니다: {prompt_path}")

        with open(prompt_path, encoding="utf-8") as f:
            prompt_text = f.read().strip()

        image_data_uri = self._image_to_data_uri(image_path)

        response = self.client.image_to_video.create(
            model="gen3a_turbo",
            prompt_image=image_data_uri,
            prompt_text=prompt_text,
            ratio="768:1280",
            duration=5,
        )

        task_id = response.id
        logging.info("RunwayML 작업 시작됨: Task ID = %s", task_id)
        time.sleep(20)

        while True:
            task = self.client.tasks.retrieve(task_id)
            if task.status in {"SUCCEEDED", "FAILED"}:
                break
            logging.info("현재 상태: %s, 20초 후 다시 확인...", task.status)
            time.sleep(20)

        if task.status == "SUCCEEDED" and task.output:
            video_url = task.output[0]
            self._download_video(video_url)
        else:
            raise RuntimeError(f"영상 생성 실패: 상태 = {task.status}")

    def _download_video(self, video_url: str) -> None:
        """영상 URL에서 실제 mp4 파일을 다운로드하여 run_dir에 저장"""
        output_path = os.path.join(self.run_dir, "output_story_video.mp4")

        response = requests.get(video_url, stream=True)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info("영상 다운로드 완료: %s", output_path)
        else:
            raise ConnectionError(
                f"영상 다운로드 실패: 상태 코드 = {response.status_code}"
            )
