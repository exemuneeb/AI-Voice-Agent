"""
Speech-to-Text using Whisper.

Supports two providers behind the same OpenAI-compatible API shape:
  - "groq"   -> hosted whisper-large-v3 (fast, generous free tier)
  - "openai" -> whisper-1

Both accept common browser recording formats directly (webm/ogg/wav/mp3/m4a),
so no local ffmpeg conversion step is required.
"""

import logging
from openai import OpenAI

from config import settings

logger = logging.getLogger("voice-agent.stt")


class TranscriptionError(Exception):
    pass


def _get_client() -> OpenAI:
    if settings.STT_PROVIDER == "groq":
        return OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
    if settings.STT_PROVIDER == "openai":
        return OpenAI(api_key=settings.OPENAI_API_KEY)
    raise ValueError(f"Unsupported STT_PROVIDER: {settings.STT_PROVIDER}")


def transcribe(file_path: str) -> str:
    """Transcribes an audio file on disk and returns the recognized text."""
    client = _get_client()
    model = (
        settings.STT_MODEL_GROQ
        if settings.STT_PROVIDER == "groq"
        else settings.STT_MODEL_OPENAI
    )

    try:
        with open(file_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="text",
            )
        # response_format="text" returns a plain string on both providers'
        # OpenAI-compatible SDK path; guard against SDK object variants too.
        text = result if isinstance(result, str) else getattr(result, "text", "")
        return text.strip()
    except Exception as exc:
        logger.exception("Transcription failed")
        raise TranscriptionError(str(exc)) from exc
