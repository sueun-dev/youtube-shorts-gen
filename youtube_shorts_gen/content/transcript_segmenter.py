import logging
import textwrap

from openai import OpenAI


class TranscriptSegmenter:
    """Generates conversational script segments suitable for YouTube Shorts."""

    _WORDS_PER_CHUNK = 500
    _MODEL = "gpt-3.5-turbo"

    def __init__(self, client: OpenAI) -> None:
        """Create an OpenAI client and define the system prompt."""
        self.client = client
        self.system_prompt = textwrap.dedent(
            """
            You are a transcript expert who creates engaging YouTube Shorts scripts.

            Task:
              1. Produce a cohesive three-minute script (≈ 400–450 words).
              2. Keep a natural, conversational tone.
              3. If earlier content is given, ensure continuity.
              4. Each script must work as a standalone YouTube Short.
            """
        )

    def _chat_completion(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Send a chat completion request and return the trimmed response text."""
        try:
            response = self.client.chat.completions.create(
                model=self._MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if not response.choices or not response.choices[0].message.content:
                logging.error("OpenAI response contained no usable content")
                return ""
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logging.error("OpenAI request failed: %s", exc)
            return ""

    def _split_into_chunks(self, transcript: str) -> list[str]:
        """Divide the transcript into word chunks of roughly equal size."""
        words = transcript.split()
        if len(words) <= self._WORDS_PER_CHUNK:
            return [transcript]

        chunks: list[str] = []
        for start in range(0, len(words), self._WORDS_PER_CHUNK):
            end = start + self._WORDS_PER_CHUNK
            chunks.append(" ".join(words[start:end]))

        trailing = len(words) % self._WORDS_PER_CHUNK
        if len(chunks) > 1 and trailing < 100:
            chunks[-2] = f"{chunks[-2]} {chunks[-1]}"
            chunks.pop()

        logging.info("Created %d chunks from %d words", len(chunks), len(words))
        return chunks

    def _create_segment(
        self,
        chunk: str,
        previous_summaries: list[str] | None = None,
    ) -> str:
        """Generate a single Shorts-ready script segment from a chunk."""
        context = ""
        if previous_summaries:
            context = "이전 컨텐츠 요약:\n" + "\n".join(previous_summaries) + "\n\n"

        user_prompt = textwrap.dedent(
            f"""
            {context}다음은 유튜브에서 추출한 정치인의 발언 또는 정치권 해설자의 음성
            을 글로 변환한 것입니다. 제공된 글을 분석한 뒤, 이 인물이 누구에 대해 어떤
            주제로 이야기하고 있는지 핵심만 간결하게 요약하여 설명하세요.

            {chunk}

            요약 형식:
              - ‘안녕하세요, 정치뉴스를 전해드리는 정쇼츠입니다.’로 시작
              - 핵심 내용 요약 (약 1 분 분량)
              - 정치인의 발언·주장 강조 (정치인 이름 포함)
              - 자연스러운 한국어 구어체
              - ‘지금까지 주요 정치 이슈를 정리해드렸습니다.’로 마무리
            """
        )

        return self._chat_completion(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1_000,
        )

    def _create_summary(self, segment: str) -> str:
        """Return a concise 50–100-word summary of a segment."""
        prompt = (
            "다음 정치 뉴스 스크립트의 핵심 내용을 50-100단어로 매우 간결하게"
            f" 요약해주세요:\n\n{segment}"
        )
        return self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )

    def segment_transcript(self, transcript: str) -> list[str]:
        """Convert a full transcript into a list of Shorts-ready script segments."""
        if not transcript or len(transcript.strip()) < 30:
            logging.error("Transcript is too short or empty")
            return []

        chunks = self._split_into_chunks(transcript)
        logging.info("Split transcript into %d chunks", len(chunks))

        scripts: list[str] = []
        summaries: list[str] = []

        for index, chunk in enumerate(chunks, start=1):
            logging.info("Processing chunk %d/%d", index, len(chunks))

            segment = self._create_segment(chunk, summaries or None)
            if not segment:
                continue

            scripts.append(segment)

            summary = self._create_summary(segment)
            if summary:
                summaries.append(summary)
                if len(summaries) > 2:
                    summaries.pop(0)

        logging.info("Successfully generated %d script segments", len(scripts))
        return scripts
