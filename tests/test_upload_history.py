"""Tests for youtube_shorts_gen.upload.upload_history.UploadHistory."""

import json

from youtube_shorts_gen.upload.upload_history import UploadHistory


def test_init_creates_missing_file_with_empty_shape(tmp_path):
    """A fresh history file is created with the empty {"uploads": []} shape."""
    history_file = tmp_path / "h.json"
    assert not history_file.exists()

    history = UploadHistory(history_file=str(history_file))

    assert history_file.exists()
    assert history.load_history() == {"uploads": []}


def test_load_history_missing_file_returns_empty_shape(tmp_path):
    """load_history returns the empty shape when no entries exist yet."""
    history = UploadHistory(history_file=str(tmp_path / "h.json"))

    assert history.load_history() == {"uploads": []}


def test_add_upload_then_is_duplicate_title(tmp_path):
    """A title added to history is reported as a duplicate."""
    history = UploadHistory(history_file=str(tmp_path / "h.json"))

    assert history.is_duplicate_title("My Title") is False

    history.add_upload("My Title", "http://example.com/v", "Once upon a time")

    assert history.is_duplicate_title("My Title") is True


def test_is_duplicate_title_is_case_sensitive(tmp_path):
    """Title matching is exact/case-sensitive, so casing differences are unique."""
    history = UploadHistory(history_file=str(tmp_path / "h.json"))
    history.add_upload("My Title", "http://example.com/v", "story")

    assert history.is_duplicate_title("My Title") is True
    assert history.is_duplicate_title("my title") is False
    assert history.is_duplicate_title("MY TITLE") is False


def test_add_upload_persists_fields_and_truncates_long_story(tmp_path):
    """add_upload writes title/url/date and truncates long story snippets."""
    history_file = tmp_path / "h.json"
    history = UploadHistory(history_file=str(history_file))

    long_story = "x" * 250
    history.add_upload("Title", "http://example.com/v", long_story)

    data = json.loads(history_file.read_text(encoding="utf-8"))
    assert len(data["uploads"]) == 1
    entry = data["uploads"][0]
    assert entry["title"] == "Title"
    assert entry["url"] == "http://example.com/v"
    assert entry["story_snippet"] == "x" * 100 + "..."
    assert "upload_date" in entry


def test_add_upload_keeps_short_story_untruncated(tmp_path):
    """Short stories are stored verbatim with no ellipsis."""
    history = UploadHistory(history_file=str(tmp_path / "h.json"))

    history.add_upload("T", "u", "short story")

    entry = history.load_history()["uploads"][0]
    assert entry["story_snippet"] == "short story"


def test_save_load_round_trip(tmp_path):
    """save_history then load_history returns the same structure."""
    history = UploadHistory(history_file=str(tmp_path / "h.json"))

    payload = {
        "uploads": [
            {
                "title": "A",
                "url": "uA",
                "story_snippet": "s",
                "upload_date": "2026-01-01T00:00:00",
            }
        ]
    }
    history.save_history(payload)

    assert history.load_history() == payload


def test_get_recent_uploads_orders_newest_first(tmp_path):
    """get_recent_uploads sorts by upload_date descending."""
    history = UploadHistory(history_file=str(tmp_path / "h.json"))
    history.save_history(
        {
            "uploads": [
                {"title": "old", "url": "u1", "upload_date": "2026-01-01T00:00:00"},
                {"title": "new", "url": "u2", "upload_date": "2026-03-01T00:00:00"},
                {"title": "mid", "url": "u3", "upload_date": "2026-02-01T00:00:00"},
            ]
        }
    )

    recent = history.get_recent_uploads()
    titles = [u["title"] for u in recent]
    assert titles == ["new", "mid", "old"]


def test_get_recent_uploads_respects_limit(tmp_path):
    """get_recent_uploads returns at most `limit` entries, newest first."""
    history = UploadHistory(history_file=str(tmp_path / "h.json"))
    history.save_history(
        {
            "uploads": [
                {"title": f"t{i}", "url": "u", "upload_date": f"2026-01-0{i}T00:00:00"}
                for i in range(1, 6)
            ]
        }
    )

    recent = history.get_recent_uploads(limit=2)
    assert len(recent) == 2
    assert [u["title"] for u in recent] == ["t5", "t4"]


def test_get_recent_uploads_empty_history(tmp_path):
    """An empty history yields an empty recent-uploads list."""
    history = UploadHistory(history_file=str(tmp_path / "h.json"))

    assert history.get_recent_uploads() == []


def test_load_history_corrupted_file_returns_empty_without_raising(tmp_path):
    """A corrupted JSON file is recovered to the empty shape without raising."""
    history_file = tmp_path / "h.json"
    history = UploadHistory(history_file=str(history_file))

    # Corrupt the file with non-JSON garbage.
    history_file.write_text("{not valid json!!!", encoding="utf-8")

    result = history.load_history()

    assert result == {"uploads": []}
    # The recovery also rewrote the file with the empty shape.
    assert json.loads(history_file.read_text(encoding="utf-8")) == {"uploads": []}


def test_is_duplicate_title_on_corrupted_file(tmp_path):
    """is_duplicate_title degrades gracefully when the file is corrupted."""
    history_file = tmp_path / "h.json"
    history = UploadHistory(history_file=str(history_file))
    history_file.write_text("garbage", encoding="utf-8")

    assert history.is_duplicate_title("anything") is False
