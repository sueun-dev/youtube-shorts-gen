import logging
import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Look for client_secrets.json in multiple locations
MODULE_DIR = Path(__file__).parent
PROJECT_ROOT = MODULE_DIR.parent
POSSIBLE_CLIENT_SECRET_PATHS = [
    MODULE_DIR / "client_secrets.json",  # youtube_shorts_gen/client_secrets.json
    PROJECT_ROOT / "client_secrets.json",  # project_root/client_secrets.json
    Path("client_secrets.json")  # Current working directory
]

for path in POSSIBLE_CLIENT_SECRET_PATHS:
    if path.exists():
        CLIENT_SECRETS_FILE = str(path)
        break
else:
    CLIENT_SECRETS_FILE = str(MODULE_DIR / "client_secrets.json")

TOKEN_FILE = str(MODULE_DIR / "token.pickle")


class YouTubeUploader:
    def __init__(
        self,
        run_dir: str,
        category_id: str = "22",
        privacy_status: str = "public",
        default_tags: list[str] | None = None,
    ):
        self.run_dir = run_dir
        self.prompt_path = os.path.join(run_dir, "story_prompt.txt")
        self.video_path = os.path.join(run_dir, "final_story_video.mp4")
        self.category_id = category_id
        self.privacy_status = privacy_status
        
        # 기본 태그 사용
        if default_tags is None:
            default_tags = ["AI short", "YouTube Shorts", "OpenAI", "RunwayML", "gTTS"]
        self.tags = default_tags
        self.creds = self._load_credentials()
        if self.creds is None:
            self.youtube = None
        else:
            self.youtube = build("youtube", "v3", credentials=self.creds)

    def _load_credentials(self) -> object | None:
        """Load OAuth 2.0 credentials for YouTube API.
        
        Returns:
            OAuth credentials or None if client_secrets.json is missing.
        """
        creds = None

        if not os.path.exists(CLIENT_SECRETS_FILE):
            logging.warning(
                "client_secrets.json not found at %s. YouTube upload disabled.",
                CLIENT_SECRETS_FILE
            )
            return None

        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "rb") as token:
                    creds = pickle.load(token)
            except (pickle.PickleError, EOFError) as e:
                logging.warning("Could not load existing token: %s", e)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logging.error("Error refreshing credentials: %s", e)
                    return None
            else:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CLIENT_SECRETS_FILE, SCOPES
                    )
                    creds = flow.run_local_server(port=0, prompt="consent")

                    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
                    with open(TOKEN_FILE, "wb") as token:
                        pickle.dump(creds, token)
                except Exception as e:
                    logging.error("Error obtaining new credentials: %s", e)
                    return None

        return creds

    def upload(self) -> str | None:
        """Upload the video to YouTube.
        
        Returns:
            The YouTube video URL or None if upload is disabled.
        """
        if self.youtube is None:
            logging.warning("YouTube upload disabled due to missing credentials.")
            return None

        if not os.path.exists(self.video_path):
            logging.error("Video file not found: %s", self.video_path)
            return None

        with open(self.prompt_path, encoding="utf-8") as f:
            story = f.read().strip()

        title = story.split(".")[0][:90] + "..."
        description = f"{story}\n\nGenerated with GPT, RunwayML, and gTTS."

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": self.tags,
                "categoryId": self.category_id,
            },
            "status": {
                "privacyStatus": self.privacy_status,
            }
        }

        logging.info("Starting YouTube upload: %s", self.video_path)
        media = MediaFileUpload(self.video_path, mimetype="video/mp4", resumable=True)
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = request.execute()
        video_url = f"https://www.youtube.com/watch?v={response['id']}"
        logging.info("✅ Uploaded to: %s", video_url)
        return video_url
