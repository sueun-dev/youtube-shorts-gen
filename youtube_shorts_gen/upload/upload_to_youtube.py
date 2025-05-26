import logging
import pickle
import time
from pathlib import Path
from typing import Any, Final

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from youtube_shorts_gen.upload.upload_history import UploadHistory

# YouTube API scopes required for uploading videos
SCOPES: Final[list[str]] = ["https://www.googleapis.com/auth/youtube.upload"]

# Locate client_secrets.json in various possible locations
MODULE_DIR: Final[Path] = Path(__file__).parent
PROJECT_ROOT: Final[Path] = MODULE_DIR.parent
POSSIBLE_CLIENT_SECRET_PATHS: Final[list[Path]] = [
    MODULE_DIR / "client_secrets.json",  # youtube_shorts_gen/client_secrets.json
    PROJECT_ROOT / "client_secrets.json",  # project_root/client_secrets.json
    Path("client_secrets.json"),  # Current working directory
]

# Find the first available client_secrets.json file
for path in POSSIBLE_CLIENT_SECRET_PATHS:
    if path.exists():
        CLIENT_SECRETS_FILE: str = str(path)
        break
else:
    CLIENT_SECRETS_FILE: str = str(MODULE_DIR / "client_secrets.json")

# Path to store OAuth token
TOKEN_FILE: Final[str] = str(MODULE_DIR / "token.pickle")


class YouTubeUploader:
    def __init__(
        self,
        run_dir: str,
        category_id: str = "22",  # 22 = People & Blogs in YouTube
        privacy_status: str = "public",
        default_tags: list[str] | None = None,
    ):
        """Initialize the YouTube uploader.

        Args:
            run_dir: Directory containing the video and story files
            category_id: YouTube category ID (default: 22 for People & Blogs)
            privacy_status: Video privacy setting (public, unlisted, private)
            default_tags: Tags to apply to the video
        """
        self.run_dir = Path(run_dir)
        self.prompt_path = self.run_dir / "story_prompt.txt"
        self.video_path = self.run_dir / "final_story_video.mp4"
        self.category_id = category_id
        self.privacy_status = privacy_status

        # Use default tags if none provided
        if default_tags is None:
            default_tags = ["AI short", "YouTube Shorts", "OpenAI", "RunwayML", "gTTS"]
        self.tags = default_tags

        # Initialize upload history tracker
        self.history = UploadHistory()

        # Initialize YouTube API client
        self.creds = self._load_credentials()
        if self.creds is None:
            self.youtube = None
        else:
            self.youtube = build("youtube", "v3", credentials=self.creds)

    def _load_credentials(self) -> Any | None:
        """Load OAuth 2.0 credentials for YouTube API.

        Attempts to load existing credentials from token file,
        refreshes expired credentials, or initiates OAuth flow
        if necessary.

        Returns:
            OAuth credentials object or None if authentication fails
        """
        creds = None

        # Check if client secrets file exists
        if not Path(CLIENT_SECRETS_FILE).exists():
            logging.warning(
                "client_secrets.json not found at %s. YouTube upload disabled.",
                CLIENT_SECRETS_FILE,
            )
            return None

        # Try to load existing token
        token_path = Path(TOKEN_FILE)
        if token_path.exists():
            try:
                with open(token_path, "rb") as token:
                    creds = pickle.load(token)
            except (pickle.PickleError, EOFError) as e:
                logging.warning("Could not load existing token: %s", e)

        # Refresh or obtain new credentials if needed
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

                    # Save credentials for future use
                    token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(token_path, "wb") as token:
                        pickle.dump(creds, token)
                except Exception as e:
                    logging.error("Error obtaining new credentials: %s", e)
                    return None

        return creds

    def upload(self) -> str | None:
        """Upload the video to YouTube.

        Returns:
            The YouTube video URL or None if upload fails or is disabled

        Raises:
            FileNotFoundError: If video or prompt files are missing
        """
        if self.youtube is None:
            logging.warning("YouTube upload disabled due to missing credentials.")
            return None

        # Verify video file exists
        if not self.video_path.exists():
            logging.error("Video file not found: %s", self.video_path)
            return None

        # Read story content for video title and description
        story = self.prompt_path.read_text(encoding="utf-8").strip()

        # Create title from first sentence (truncated to 90 chars)
        title = story.split(".")[0][:90] + "..."
        description = f"{story}\n\nGenerated with GPT, RunwayML, and gTTS."

        # Check if this title has been uploaded before
        if self.history.is_duplicate_title(title):
            logging.warning("Duplicate title detected: %s", title)
            # Modify the title to make it unique by adding a timestamp
            timestamp = int(time.time())
            title = f"{title} ({timestamp})"
            logging.info("Modified title to avoid duplicate: %s", title)

        # Prepare video metadata
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": self.tags,
                "categoryId": self.category_id,
            },
            "status": {
                "privacyStatus": self.privacy_status,
            },
        }

        # Upload the video
        logging.info("Starting YouTube upload: %s", self.video_path)
        media = MediaFileUpload(
            str(self.video_path), mimetype="video/mp4", resumable=True
        )
        request = self.youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )

        response = request.execute()
        video_url = f"https://www.youtube.com/watch?v={response['id']}"
        logging.info("✅ Uploaded to: %s", video_url)

        # Save this upload to history
        self.history.add_upload(title, video_url, story)
        logging.info("Added video to upload history")

        return video_url
