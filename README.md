# YouTube Shorts 자동 생성기 Beta Version

YouTube Shorts를 자동으로 생성하고 업로드하는 AI 기반 파이프라인입니다.

## 프로젝트 개요

이 프로젝트는 다음과 같은 작업을 자동화합니다:

1. OpenAI API를 사용하여 짧은 이야기 생성
2. 이야기에 맞는 이미지 생성
3. Runway ML을 사용하여 이미지로부터 비디오 생성
4. 텍스트 음성 변환(TTS)을 사용하여 이야기 오디오 생성
5. 비디오와 오디오 동기화
6. 최종 비디오를 YouTube에 자동 업로드

## 설치 방법

### 필수 요구 사항

- Python 3.13+
- Poetry (패키지 관리)
- FFmpeg (비디오/오디오 처리)
- OpenAI API 키
- Runway ML API 키
- Google API 인증 정보

### 설치 단계

1. 저장소 클론하기:
   ```bash
   git clone https://github.com/yourusername/youtube-shorts.git
   cd youtube-shorts
   ```

2. Poetry를 사용하여 의존성 설치:
   ```bash
   poetry install
   ```

3. API 키 획득 및 환경 변수 설정:
   
   - OpenAI API 키는 [OpenAI 플랫폼](https://platform.openai.com/settings/organization/general)에서 얻을 수 있습니다.
   - Runway ML API 키는 [Runway 개발자 문서](https://docs.dev.runwayml.com/)에서 계정 생성 후 얻을 수 있습니다.
   
   `.env` 파일을 생성하고 다음과 같이 설정합니다:
   ```
   OPENAI_API_KEY=your_openai_api_key
   RUNWAY_API_KEY=your_runway_api_key
   ```

4. Google API 설정:
   - [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
   - YouTube Data API v3 활성화
   - OAuth 2.0 클라이언트 ID 생성
   - 다운로드한 인증 정보를 `client_secrets.json`으로 저장소 루트에 저장

## 사용 방법

### 단일 실행

프로젝트 루트 디렉토리에서 다음 명령어로 실행합니다:

```bash
poetry run python main.py
```

첫 실행 시 몇분 뒤 Google 계정 인증을 요청하는 브라우저 창이 열립니다. 인증 후에는 토큰이 저장되어 다음 실행부터는 자동으로 진행됩니다.

### 자동 실행 모드

기본적으로 프로그램은 10분 간격으로 새로운 YouTube Shorts를 생성하고 업로드합니다. 이 설정은 `youtube_shorts_gen/main.py` 파일에서 변경할 수 있습니다.

## 주요 컴포넌트

### 1. 스토리 및 이미지 생성 (`youtube_script_gen.py`)
OpenAI의 GPT 모델을 사용하여 짧은 이야기를 생성하고, DALL-E 모델을 사용하여 해당 이야기에 맞는 이미지를 생성합니다.

### 2. 비디오 생성 (`runway.py`)
Runway ML의 Gen-2 모델을 사용하여 이미지에서 움직이는 비디오를 생성합니다.

### 3. 오디오 동기화 (`sync_video_with_tts.py`)
gTTS를 사용하여 텍스트를 음성으로 변환하고, FFmpeg를 사용하여 비디오와 오디오를 동기화합니다.

### 4. YouTube 업로드 (`upload_to_youtube.py`)
Google API를 사용하여 최종 비디오를 YouTube에 자동으로 업로드합니다.

## 문제 해결

### 일반적인 오류

1. **API 키 오류**: `.env` 파일에 올바른 API 키가 설정되어 있는지 확인하세요.
2. **FFmpeg 오류**: FFmpeg가 설치되어 있고 PATH에 추가되어 있는지 확인하세요.
3. **Google 인증 오류**: `client_secrets.json` 파일이 올바른지, 그리고 YouTube Data API가 활성화되어 있는지 확인하세요.
4. **디렉토리 오류**: 실행 전에 `runs` 디렉토리가 존재하는지 확인하세요. 없다면 자동으로 생성됩니다.

### 로그 확인

각 단계에서 로그가 콘솔에 출력됩니다. 오류 발생 시 메시지를 확인하여 문제를 파악할 수 있습니다.

## 코드 품질

프로젝트는 다음과 같은 도구를 사용하여 코드 품질을 유지합니다:

- **Ruff**: PEP8 스타일 가이드 준수, 린팅, 포맷 검사
- **Pyright**: 정적 타입 검사
- **pytest**: 자동화된 테스트

```bash
# 코드 품질 검사
poetry run ruff check .

# 타입 검사
poetry run pyright

# 테스트 실행
poetry run python run_tests.py
```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 주의사항

- 생성된 콘텐츠에 대한 모든 책임은 사용자에게 있습니다.
- API 사용량은 해당 서비스의 사용량 제한 및 과금 정책을 따릅니다.
- YouTube의 정책을 준수하는 콘텐츠만 업로드하세요.
