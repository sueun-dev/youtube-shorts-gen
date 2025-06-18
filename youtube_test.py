#!/usr/bin/env python3
"""
Simple test script for youtube-transcript-api v1.0.3+
"""
import logging
import sys

from youtube_transcript_api import YouTubeTranscriptApi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def test_fetch_transcript(video_id):
    """
    Test the basic functionality of getting a transcript using the new API
    """
    logging.info(f"Testing fetch transcript for video ID: {video_id}")
    
    try:
        transcript_api = YouTubeTranscriptApi()
        fetched_transcript = transcript_api.fetch(video_id)
        logging.info(f"Success! Found {len(fetched_transcript)} transcript snippets")
        logging.info(
            f"Language: {fetched_transcript.language} "
            f"({fetched_transcript.language_code})"
        )
        logging.info(f"Generated: {fetched_transcript.is_generated}")
        
        logging.info("First 3 snippets:")
        for i, snippet in enumerate(fetched_transcript.snippets[:3]):
            logging.info(
                f"{i+1}. {snippet.text} "
                f"(Start: {snippet.start}, Duration: {snippet.duration})"
            )
        
        return True
    except Exception as e:
        logging.error(f"Error fetching transcript: {e}")
        return False

def test_list_transcripts(video_id):
    """
    Test listing available transcripts with the new API
    """
    logging.info(f"Testing list transcripts for video ID: {video_id}")
    
    try:
        transcript_api = YouTubeTranscriptApi()
        transcript_list = transcript_api.list(video_id)
        logging.info("Success! Available transcripts:")
        
        for transcript in transcript_list:
            logging.info(
                f"  - Language: {transcript.language} "
                f"({transcript.language_code})"
            )
            logging.info(
                f"    Generated: {transcript.is_generated}, "
                f"Translatable: {transcript.is_translatable}"
            )
        
        return True
    except Exception as e:
        logging.error(f"Error listing transcripts: {e}")
        return False

if __name__ == "__main__":
    # Use ternary operator as suggested by SIM108
    video_id = sys.argv[1] if len(sys.argv) > 1 else "HEgwZ3jIedU"
        
    logging.info(f"Testing youtube-transcript-api v1.0.3+ with video ID: {video_id}")
    
    test_fetch_transcript(video_id)
    test_list_transcripts(video_id)
