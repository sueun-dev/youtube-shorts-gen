# upload_to_youtube.py

import os
import pickle

import googleapiclient.discovery
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaFileUpload

SCOPES              = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_FILE          = "token.pickle"


def _get_credentials():
    creds = None
    # 기존에 저장된 토큰이 있으면 로드
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # 토큰이 없거나 유효하지 않으면 갱신 또는 새 인증
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                SCOPES
            )
            creds = flow.run_local_server(port=0, prompt="consent")
        # 갱신된 토큰 저장
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return creds


def upload_video(run_dir: str):
    prompt_path = os.path.join(run_dir, "story_prompt.txt")
    final_video = os.path.join(run_dir, "final_story_video.mp4")

    with open(prompt_path) as f:
        story = f.read().strip()

    title       = story.split(".")[0][:90] + "..."
    description = f"{story}\n\nGenerated with GPT, RunwayML, and gTTS."
    tags        = ["AI short", "YouTube Shorts", "OpenAI", "RunwayML", "gTTS"]

    creds   = _get_credentials()
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        tags,
            "categoryId":  "22",
        },
        "status": {"privacyStatus": "public"}
    }

    media   = MediaFileUpload(final_video, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(
        part="snippet,status", 
        body=body, 
        media_body=media
    )
    response = request.execute()

    print(f"✅ Uploaded to: https://www.youtube.com/watch?v={response['id']}")
