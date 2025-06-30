# YouTube Shorts 자동 생성기

인공지능과 인터넷 콘텐츠를 활용하여 YouTube Shorts 비디오를 자동으로 생성하고 업로드하는 프로그램입니다.

## 주요 기능

- AI로 스토리와 이미지 생성
- 인터넷 기사·블로그 등에서 콘텐츠 크롤링
- 연도별 변화를 보여주는 타임-lapse 숏츠 생성
- 이미지와 음성을 결합한 YouTube Shorts 비디오 제작
- 완성된 비디오를 YouTube에 자동 업로드

## 설치 방법

### 필요한 것들

- Python 3.10 이상
- FFmpeg
- API 키들:
  - OpenAI API 키
  - Runway ML API 키
  - YouTube API 인증 정보

### 설치 과정

1. 저장소 클론 및 이동:
   ```bash
   git clone https://github.com/사용자명/youtube-shorts.git
   cd youtube-shorts
   ```

2. 패키지 설치:
   ```bash
   poetry install
   poetry shell
   ```

3. API 키 설정:
   - `.env` 파일 생성:
   ```
   OPENAI_API_KEY=your_openai_api_key
   RUNWAY_API_KEY=your_runway_api_key
   ```

4. YouTube 업로드 설정:
   - Google Cloud Console에서 YouTube Data API v3 활성화
   - OAuth 2.0 인증 정보를 `client_secrets.json`에 저장

## 실행 방법

1. 프로그램 실행:
   ```bash
   python main.py
   ```
   또는 Poetry 사용 시:
   ```bash
   poetry run python main.py
   ```

2. 콘텐츠 생성 선택:
   - 프로그램이 시작되면 네 가지 옵션 중 하나를 선택해야 합니다:
     - `1`: AI가 새로운 스토리 생성
     - `2`: 인터넷에서 콘텐츠 가져오기
     - `3`: YouTube 영상 자막을 활용한 숏츠 생성
     - `4`: Time-lapse Video — 연도(또는 시간)별 이미지·영상으로 변화를 보여주는 숏츠 생성

3. 옵션 4 (Time-lapse) 추가 정보:
   1. 주제 프롬프트와 연도 범위 입력
   2. OpenAI 이미지 API로 연도별 이미지를 생성·캐시
   3. 이미지 간 보간 프레임(3장, 0.033 s) 생성 → 부드러운 전환
   4. FFmpeg로 1080×1920, 30 fps 영상 합성 및 배경 음악 결합
   5. 선택 시 YouTube에 자동 업로드

4. 자동 처리:
   - 선택한 옵션에 따라 자동으로 다음 과정이 진행됩니다:
     - 이미지 생성
     - 음성 생성
     - 비디오 생성
     - YouTube 업로드 (설정된 경우)

4. 처음 실행 시 주의사항:
   - YouTube 업로드 시에는 Google 계정 인증 창이 나타납니다.
   - FFmpeg가 설치되어 있는지 확인하세요.

## 출력 파일

프로그램이 실행되면 `runs/` 폴더 안에 날짜와 시간으로 된 폴더가 생성됩니다 (예: `runs/2025-05-27_15-22-53/`).

- AI 옵션 선택 시: 최종적으로 `final_story_video.mp4` 파일이 생성됩니다.
- 인터넷 옵션 선택 시: 이미지, 오디오, 비디오가 각각 생성되고 최종적으로 `final_story_video.mp4` 파일이 생성됩니다.

## 자주 발생하는 문제 해결

- **API 키 오류**: `.env` 파일에 유효한 API 키가 있는지 확인하세요.
- **FFmpeg 오류**: 시스템에 FFmpeg가 설치되어 있는지 확인하세요.
- **YouTube 업로드 오류**: `client_secrets.json` 파일이 올바른지 확인하세요.

## 관련 정보

- OpenAI와 Runway ML API는 사용량에 따라 비용이 발생할 수 있습니다.
- 리넩스에서는 FFmpeg 설치를 위해 `apt-get install ffmpeg`를 실행하세요.



 링크 던지면 여기서 영상 가져와서 숏츠로 잘라냄 (상요자가 시간을 정하고)
잘라주고
