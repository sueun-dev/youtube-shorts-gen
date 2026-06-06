"""Tests for the YouTube uploader (no real Google API calls)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from youtube_shorts_gen.upload.upload_history import UploadHistory
from youtube_shorts_gen.upload.upload_to_youtube import YouTubeUploader
from youtube_shorts_gen.utils.config import (
    FINAL_VIDEO_FILENAME,
    STORY_PROMPT_FILENAME,
    YOUTUBE_CATEGORY_ID,
    YOUTUBE_DEFAULT_TAGS,
    YOUTUBE_PRIVACY_STATUS,
)

_MODULE = "youtube_shorts_gen.upload.upload_to_youtube"


def _make_uploader(run_dir, history_file, *, creds=None):
    """Construct a YouTubeUploader with credentials and history mocked.

    Patches ``_load_credentials`` to return ``creds`` (None by default) and
    points ``UploadHistory`` at ``history_file`` so nothing touches the repo.
    """
    history = UploadHistory(history_file=str(history_file))
    with (
        patch.object(YouTubeUploader, "_load_credentials", return_value=creds),
        patch(f"{_MODULE}.UploadHistory", return_value=history),
        patch(f"{_MODULE}.build") as mock_build,
    ):
        uploader = YouTubeUploader(str(run_dir))
    return uploader, mock_build


def _write_story(run_dir, story):
    (Path(run_dir) / STORY_PROMPT_FILENAME).write_text(story, encoding="utf-8")


def _write_video(run_dir):
    (Path(run_dir) / FINAL_VIDEO_FILENAME).write_bytes(b"\x00\x00fakevideo")


# --------------------------------------------------------------------------- #
# Constructor defaults
# --------------------------------------------------------------------------- #
def test_constructor_pulls_defaults_from_config(tmp_path):
    uploader, mock_build = _make_uploader(tmp_path, tmp_path / "hist.json")

    assert uploader.category_id == YOUTUBE_CATEGORY_ID
    assert uploader.privacy_status == YOUTUBE_PRIVACY_STATUS
    assert uploader.tags == YOUTUBE_DEFAULT_TAGS
    assert uploader.run_dir == tmp_path
    assert uploader.prompt_path == tmp_path / STORY_PROMPT_FILENAME
    assert uploader.video_path == tmp_path / FINAL_VIDEO_FILENAME
    # No credentials -> no youtube service is built.
    assert uploader.youtube is None
    mock_build.assert_not_called()


def test_constructor_overrides_and_default_tags_fallback(tmp_path):
    history = UploadHistory(history_file=str(tmp_path / "hist.json"))
    with (
        patch.object(YouTubeUploader, "_load_credentials", return_value=None),
        patch(f"{_MODULE}.UploadHistory", return_value=history),
        patch(f"{_MODULE}.build"),
    ):
        uploader = YouTubeUploader(
            str(tmp_path),
            category_id="27",
            privacy_status="unlisted",
            default_tags=None,
        )

    assert uploader.category_id == "27"
    assert uploader.privacy_status == "unlisted"
    # default_tags=None falls back to the config default list.
    assert uploader.tags == YOUTUBE_DEFAULT_TAGS


def test_constructor_uses_explicit_tags(tmp_path):
    history = UploadHistory(history_file=str(tmp_path / "hist.json"))
    with (
        patch.object(YouTubeUploader, "_load_credentials", return_value=None),
        patch(f"{_MODULE}.UploadHistory", return_value=history),
        patch(f"{_MODULE}.build"),
    ):
        uploader = YouTubeUploader(str(tmp_path), default_tags=["only", "these"])

    assert uploader.tags == ["only", "these"]


def test_constructor_builds_service_when_creds_present(tmp_path):
    history = UploadHistory(history_file=str(tmp_path / "hist.json"))
    fake_creds = MagicMock()
    fake_service = MagicMock()
    with (
        patch.object(
            YouTubeUploader, "_load_credentials", return_value=fake_creds
        ),
        patch(f"{_MODULE}.UploadHistory", return_value=history),
        patch(f"{_MODULE}.build", return_value=fake_service) as mock_build,
    ):
        uploader = YouTubeUploader(str(tmp_path))

    assert uploader.youtube is fake_service
    mock_build.assert_called_once_with(
        "youtube", "v3", credentials=fake_creds
    )


# --------------------------------------------------------------------------- #
# upload(): credential / file failure paths
# --------------------------------------------------------------------------- #
def test_upload_returns_none_without_credentials(tmp_path):
    uploader, _ = _make_uploader(tmp_path, tmp_path / "hist.json")
    _write_story(tmp_path, "line one\nMy Title")
    _write_video(tmp_path)

    # youtube is None because credentials could not be loaded.
    assert uploader.upload() is None


def test_upload_returns_none_when_video_missing(tmp_path):
    history_file = tmp_path / "hist.json"
    fake_creds = MagicMock()
    uploader, _ = _make_uploader(tmp_path, history_file, creds=fake_creds)
    # Provide a fake youtube service so we get past the creds check.
    uploader.youtube = MagicMock()
    _write_story(tmp_path, "line one\nMy Title")
    # Note: no video file written.

    assert uploader.upload() is None
    uploader.youtube.videos.assert_not_called()


# --------------------------------------------------------------------------- #
# upload(): successful upload path
# --------------------------------------------------------------------------- #
def _drive_successful_upload(uploader, video_id="abc123"):
    """Wire a fake youtube service whose execute() returns a video id."""
    fake_youtube = MagicMock()
    request = fake_youtube.videos.return_value.insert.return_value
    request.execute.return_value = {"id": video_id}
    uploader.youtube = fake_youtube
    with patch(f"{_MODULE}.MediaFileUpload") as mock_media:
        url = uploader.upload()
    return url, fake_youtube, mock_media


def test_upload_success_returns_url_and_records_history(tmp_path):
    history_file = tmp_path / "hist.json"
    uploader, _ = _make_uploader(
        tmp_path, history_file, creds=MagicMock()
    )
    _write_story(tmp_path, "first line\nSecond Line Title")
    _write_video(tmp_path)

    url, fake_youtube, mock_media = _drive_successful_upload(uploader)

    assert url == "https://www.youtube.com/watch?v=abc123"
    mock_media.assert_called_once()
    # Title comes from the second line of the story.
    insert_kwargs = fake_youtube.videos.return_value.insert.call_args.kwargs
    assert insert_kwargs["body"]["snippet"]["title"] == "Second Line Title"
    assert insert_kwargs["part"] == "snippet,status"
    assert insert_kwargs["body"]["status"]["privacyStatus"] == (
        YOUTUBE_PRIVACY_STATUS
    )

    # History file updated with the new upload.
    recorded = UploadHistory(history_file=str(history_file)).load_history()
    titles = [u["title"] for u in recorded["uploads"]]
    assert "Second Line Title" in titles
    assert recorded["uploads"][0]["url"] == url


def test_upload_title_falls_back_to_first_line(tmp_path):
    history_file = tmp_path / "hist.json"
    uploader, _ = _make_uploader(
        tmp_path, history_file, creds=MagicMock()
    )
    # Only one line -> the first line is used as the title.
    _write_story(tmp_path, "Only One Line")
    _write_video(tmp_path)

    url, fake_youtube, _ = _drive_successful_upload(uploader)

    assert url == "https://www.youtube.com/watch?v=abc123"
    insert_kwargs = fake_youtube.videos.return_value.insert.call_args.kwargs
    assert insert_kwargs["body"]["snippet"]["title"] == "Only One Line"


def test_upload_dedupes_duplicate_title(tmp_path):
    history_file = tmp_path / "hist.json"
    # Pre-seed history with the title we are about to upload.
    seed = UploadHistory(history_file=str(history_file))
    seed.add_upload("Second Line Title", "https://youtu.be/old", "old story")

    uploader, _ = _make_uploader(
        tmp_path, history_file, creds=MagicMock()
    )
    _write_story(tmp_path, "first line\nSecond Line Title")
    _write_video(tmp_path)

    url, fake_youtube, _ = _drive_successful_upload(uploader, video_id="dup99")

    assert url == "https://www.youtube.com/watch?v=dup99"
    insert_kwargs = fake_youtube.videos.return_value.insert.call_args.kwargs
    sent_title = insert_kwargs["body"]["snippet"]["title"]
    # The duplicate title is suffixed with a timestamp to make it unique.
    assert sent_title.startswith("Second Line Title (")
    assert sent_title != "Second Line Title"

    recorded = UploadHistory(history_file=str(history_file)).load_history()
    assert len(recorded["uploads"]) == 2


def test_upload_returns_none_when_execute_raises(tmp_path):
    history_file = tmp_path / "hist.json"
    uploader, _ = _make_uploader(
        tmp_path, history_file, creds=MagicMock()
    )
    _write_story(tmp_path, "first line\nSecond Line Title")
    _write_video(tmp_path)

    fake_youtube = MagicMock()
    request = fake_youtube.videos.return_value.insert.return_value
    request.execute.side_effect = RuntimeError("boom")
    uploader.youtube = fake_youtube

    with patch(f"{_MODULE}.MediaFileUpload"):
        result = uploader.upload()

    assert result is None
    # Failed upload is not recorded in history.
    recorded = UploadHistory(history_file=str(history_file)).load_history()
    assert recorded["uploads"] == []
