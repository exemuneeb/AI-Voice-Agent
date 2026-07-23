"""
Text-to-Speech.

Two providers are supported:
  - "edge"       -> Microsoft Edge TTS (free, no API key required). Default.
  - "elevenlabs" -> ElevenLabs API (higher quality, but their free tier no
                    longer allows API access to voices — a paid plan is
                    required to use this provider).
"""

import asyncio
import logging
import requests
import edge_tts

from config import settings

logger = logging.getLogger("voice-agent.tts")

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class SpeechSynthesisError(Exception):
    pass


async def synthesize(text: str) -> bytes:
    """Converts text to speech and returns raw audio bytes (mp3)."""
    if settings.TTS_PROVIDER == "edge":
        return await _synthesize_edge(text)
    if settings.TTS_PROVIDER == "elevenlabs":
        return await asyncio.to_thread(_synthesize_elevenlabs, text)
    raise SpeechSynthesisError(f"Unsupported TTS_PROVIDER: {settings.TTS_PROVIDER}")


async def _synthesize_edge(text: str) -> bytes:
    try:
        communicate = edge_tts.Communicate(text, voice=settings.EDGE_VOICE)
        audio_bytes = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        if not audio_bytes:
            raise SpeechSynthesisError("Edge TTS returned no audio data.")
        return bytes(audio_bytes)
    except SpeechSynthesisError:
        raise
    except Exception as exc:
        logger.exception("Edge TTS failed")
        raise SpeechSynthesisError(str(exc)) from exc


def _synthesize_elevenlabs(text: str) -> bytes:
    if not settings.ELEVENLABS_API_KEY:
        raise SpeechSynthesisError("ELEVENLABS_API_KEY is not configured on the server.")

    url = ELEVENLABS_TTS_URL.format(voice_id=settings.ELEVENLABS_VOICE_ID)
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": settings.ELEVENLABS_MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
        "output_format": settings.ELEVENLABS_OUTPUT_FORMAT,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            logger.error("ElevenLabs error %s: %s", response.status_code, response.text[:500])
            raise SpeechSynthesisError(
                f"ElevenLabs API returned {response.status_code}: {response.text[:200]}"
            )
        return response.content
    except requests.RequestException as exc:
        logger.exception("TTS request failed")
        raise SpeechSynthesisError(str(exc)) from exc
