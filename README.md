# YouTube Shorts 자동 생성기

AI와 인터넷 콘텐츠를 활용하여 YouTube Shorts 영상을 자동으로 생성하고 업로드하는
파이프라인입니다. 스토리·이미지 생성, 음성 내레이션(TTS), 영상 합성, 업로드까지 전
과정을 자동화합니다.

## 주요 기능 (4가지 콘텐츠 모드)

1. **AI 스토리** — 무작위 프롬프트로 짧은 스토리와 이미지를 생성하고, Runway로
   영상을 만든 뒤 TTS 내레이션과 동기화합니다.
2. **인터넷 콘텐츠** — Dogdrip에서 글을 크롤링해 문장별 이미지·음성·영상을 만들고
   하나의 숏츠로 합칩니다.
3. **YouTube 자막** — YouTube 영상의 자막을 가져와 짧은 스크립트로 분할하고, 각
   세그먼트를 이미지·음성·영상으로 변환합니다.
4. **타임랩스** — 연도별 이미지를 생성하고 프레임 보간으로 부드럽게 전환되는, 시간에
   따른 변화를 보여주는 숏츠를 만듭니다.

## 설치

### 요구 사항

- Python 3.12 이상
- [FFmpeg](https://ffmpeg.org/) (영상 합성에 필요)
- API 키:
  - OpenAI API 키 (스토리·이미지 생성)
  - ElevenLabs API 키 (음성 내레이션)
  - Runway ML API 키 (이미지→영상 생성)
  - YouTube Data API v3 OAuth 인증 정보 (업로드)

### 설치 과정

```bash
git clone https://github.com/sueun-dev/youtube-shorts-gen.git
cd youtube-shorts-gen

# Poetry 사용 시
poetry install
poetry shell

# 또는 venv + pip
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 환경 변수 설정

프로젝트 루트에 `.env` 파일을 만들고 API 키를 넣습니다:

```dotenv
OPENAI_API_KEY=your_openai_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
RUNWAY_API_KEY=your_runway_api_key
```

### YouTube 업로드 설정

- Google Cloud Console에서 YouTube Data API v3를 활성화합니다.
- OAuth 2.0 클라이언트 정보를 받아 `client_secrets.json`으로 저장합니다
  (`client_secrets_template.json` 참고). 최초 실행 시 브라우저 인증 창이 뜹니다.

## 실행

```bash
python main.py
```

실행하면 콘텐츠 소스를 선택합니다:

- `1`: AI 스토리
- `2`: 인터넷 콘텐츠
- `3`: YouTube 자막
- `4`: 타임랩스 (주제 프롬프트와 연도 범위를 입력)

프로그램은 무한 루프로 동작하며, 한 번 실행이 끝나면 `SLEEP_SECONDS`(기본 120초)만큼
대기 후 다시 실행합니다.

## 출력 파일

실행할 때마다 `runs/` 아래에 타임스탬프 폴더가 생성됩니다
(예: `runs/2025-05-27_15-22-53/`). 최종 영상은 `final_story_video.mp4`로 저장되며,
설정에 따라 YouTube에 자동 업로드됩니다.

## 설정 (환경 변수로 조정 가능)

대부분의 동작은 `youtube_shorts_gen/utils/config.py`에 모여 있으며, 다음 환경 변수로
기본값을 덮어쓸 수 있습니다:

| 변수 | 설명 | 기본값 |
| --- | --- | --- |
| `OPENAI_CHAT_MODEL` | 스토리·요약용 챗 모델 | `gpt-4o-mini-2024-07-18` |
| `OPENAI_IMAGE_MODEL` | 이미지 생성 모델 | `gpt-image-1` |
| `OPENAI_IMAGE_SIZE` | 이미지 크기 | `1024x1024` |
| `OPENAI_IMAGE_QUALITY` | 이미지 품질 (`low`/`medium`/`high`) | `medium` |
| `ELEVENLABS_VOICE_ID` | TTS 음성 ID | (기본 음성) |
| `RUNWAY_MODEL` / `RUNWAY_ASPECT_RATIO` | Runway 모델·비율 | `gen3a_turbo` / `768:1280` |
| `MAX_RUNWAY_VIDEOS_PER_SEGMENT` | 세그먼트당 Runway 영상 수 | `4` |
| `SLEEP_SECONDS` | 실행 사이 대기 시간(초) | `120` |

## 개발

```bash
ruff check .      # 린트
ruff format .     # 포매팅
pyright           # 타입 검사
pytest            # 테스트
```

## 참고

- OpenAI, ElevenLabs, Runway ML API는 사용량에 따라 비용이 발생할 수 있습니다.
- 리눅스에서는 `apt-get install ffmpeg`로 FFmpeg를 설치할 수 있습니다.
