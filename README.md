# YouTube Shorts 생성기

AI를 활용하여 YouTube Shorts 비디오를 자동으로 생성하고 업로드하는 파이프라인입니다.

## 기능

- OpenAI API를 사용한 스토리 생성
- 인터넷 검색을 활용한 스토리 생성
- DALL-E를 통한 이미지 생성
- Runway ML을 사용한 비디오 생성
- 텍스트-음성 변환(TTS) 및 비디오 동기화
- 단락별 이미지-오디오 동기화
- YouTube 자동 업로드

## 설치 방법

### 필수 요구 사항

- Python 3.10+
- FFmpeg (비디오/오디오 처리)
- API 키: OpenAI, Runway ML
- YouTube API 인증 정보 (업로드 기능 사용 시)
- BeautifulSoup4 (인터넷 콘텐츠 스크래핑)

### 설치 단계

1. 저장소 클론:
   ```bash
   git clone <repository-url>
   cd youtube-shorts
   ```

2. 의존성 설치:
   ```bash
   pip install -e .
   ```
   또는 Poetry 사용 시:
   ```bash
   poetry install
   poetry shell
   ```

3. 환경 설정:
   `.env` 파일 생성 및 API 키 설정:
   ```
   OPENAI_API_KEY=your_openai_api_key
   RUNWAY_API_KEY=your_runway_api_key
   ```

4. YouTube 업로드 설정 (선택 사항):
   - `client_secrets_template.json`을 `client_secrets.json`으로 복사
   - [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
   - YouTube Data API v3 활성화 및 OAuth 2.0 인증 정보 획득
   - 인증 정보를 `client_secrets.json`에 입력

## 실행 방법

단일 실행:

```bash
python main.py
```

첫 YouTube 업로드 시 Google 인증 창이 열립니다. 인증 후에는 자동으로 진행됩니다.

## 작동 방식

프로그램은 콘텐츠 소스에 따라 다음 단계로 실행됩니다:

### AI 생성 파이프라인
1. 스토리 텍스트 생성 (OpenAI)
2. 스토리 기반 이미지 생성 (DALL-E)
3. 이미지 기반 비디오 생성 (Runway ML)
4. 오디오와 비디오 동기화
5. YouTube 업로드 (설정된 경우)

### 인터넷 검색 파이프라인
1. 인터넷에서 인기 있는 포스트 가져오기
2. 콘텐츠 요약 및 단락 분할 (OpenAI)
3. 각 단락에 대한 이미지 생성 (DALL-E)
4. 각 단락에 대한 TTS 오디오 생성
5. 단락별 이미지-오디오 동기화 및 비디오 생성
6. 모든 단락 비디오 결합
7. YouTube 업로드 (설정된 경우)

Google API를 사용하여 최종 비디오를 YouTube에 자동으로 업로드합니다.

## 출력 파일

모든 실행은 타임스탬프 폴더에 저장됩니다 (`runs/YYYY-MM-DD_HH-MM-SS/`):

### AI 생성 파이프라인
- `story_prompt.txt`: 생성된 스토리 텍스트
- `story_image.png`: 생성된 이미지
- `story_video.mp4`: Runway로 생성된 비디오
- `final_story_video.mp4`: 오디오가 포함된 최종 비디오

### 인터넷 검색 파이프라인
- `story_prompt.txt`: 생성된 스토리 텍스트
- `paragraph_image_mapping.txt`: 단락과 이미지 매핑 정보
- `images/`: 각 단락에 대한 이미지 폴더
- `audio/`: 각 단락에 대한 TTS 오디오 폴더
- `paragraph_videos/`: 각 단락에 대한 비디오 폴더
- `final_story_video.mp4`: 모든 단락 비디오가 결합된 최종 비디오

## 문제 해결

주요 오류 해결:

- **API 키**: `.env` 파일에 유효한 API 키 확인
- **FFmpeg**: 시스템에 FFmpeg 설치 여부 확인
- **디렉토리**: `runs` 디렉토리가 자동으로 생성되지 않은 경우 수동으로 생성
- **Google 인증**: `client_secrets.json` 파일 가용성 및 형식 확인

로그는 콘솔에 출력되며 오류 메시지를 확인하여 문제를 해결할 수 있습니다.

## 주의사항

- API 키를 안전하게 관리하세요
- API 사용량 및 비용에 주의하세요
- YouTube 업로드 시 저작권 및 커뮤니티 가이드라인을 준수하세요

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.


## 구현된 기능

1. 문장별로 분리하여 각 문장에 대한 이미지 생성 (GPT Image 사용) - ✅ 완료
2. TTS(Text-to-Speech) 기능 추가 - ✅ 완료
3. 문장별 이미지 표시 및 TTS와 동기화 - ✅ 완료
4. 인터넷 콘텐츠 스크래핑 및 처리 - ✅ 완료
6. 단락별 이미지-오디오 동기화 - ✅ 완료