import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Set up logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)

# Add the parent directory to the path to import the module
sys.path.append(str(Path(__file__).parent.parent))


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete YouTube Shorts generation pipeline."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary test directory
        self.test_dir = "test_runs/integration_test"
        os.makedirs(self.test_dir, exist_ok=True)
        
    def tearDown(self):
        """Clean up after each test."""
        # In a real scenario we would delete test files, but for safety we just log
        logging.info(f"Would remove test directory: {self.test_dir}")
    
    @patch('os.makedirs')
    @patch('os.path.join')
    def test_pipeline_structure(self, mock_join, mock_makedirs):
        """Test the basic structure and flow without executing actual code."""
        mock_join.return_value = "runs/2025-05-02_15-13-43"
        
        # 모듈 모킹 및 클래스 패치를 여러 줄로 나누어 구성
        with patch.dict('sys.modules', {
            'requests': MagicMock(),
            'urllib3': MagicMock(),
            'google.auth.transport.requests': MagicMock(),
            'google.oauth2.credentials': MagicMock(),
            'google.auth.exceptions': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'google_auth_oauthlib.flow': MagicMock(),
            'runwayml': MagicMock()
        }):
            # 긴 패치 경로를 분리하여 라인 길이 제한 준수
            yt_pkg = 'youtube_shorts_gen'
            script_gen_path = f'{yt_pkg}.youtube_script_gen.YouTubeScriptGenerator'
            video_gen_path = f'{yt_pkg}.runway.VideoGenerator'
            syncer_path = f'{yt_pkg}.sync_video_with_tts.VideoAudioSyncer'
            uploader_path = f'{yt_pkg}.upload_to_youtube.YouTubeUploader'
            
            with patch(script_gen_path) as MockScriptGen, \
                 patch(video_gen_path) as MockVideoGen, \
                 patch(syncer_path) as MockSync, \
                 patch(uploader_path) as MockUploader:
                
                mock_script_gen_instance = MockScriptGen.return_value
                mock_video_gen_instance = MockVideoGen.return_value
                mock_sync_instance      = MockSync.return_value
                mock_uploader_instance  = MockUploader.return_value
    
                from main import run_pipeline_once
                run_pipeline_once()
    
                mock_makedirs.assert_called_once()
                mock_script_gen_instance.run.assert_called_once()
                mock_video_gen_instance.generate.assert_called_once()
                mock_sync_instance.sync.assert_called_once()
                mock_uploader_instance.upload.assert_called_once()


if __name__ == '__main__':
    unittest.main()
