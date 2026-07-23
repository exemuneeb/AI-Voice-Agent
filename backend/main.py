"""
Voice AI Agent — FastAPI backend.

Pipeline: audio in -> Whisper STT -> LLM agent (with tool calling) -> ElevenLabs TTS -> audio out.

Run locally:
    uvicorn main:app --reload --port 8000

See README.md for full setup and deployment instructions.
"""

import base64
import json
import logging
import tempfile
import os
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import settings
from stt import transcribe, TranscriptionError
from tts import synthesize, SpeechSynthesisError
from agent import generate_reply

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("voice-agent.main")

app = FastAPI(
    title="Voice AI Agent",
    description="Real-time voice agent: Whisper STT + LLM (with tools) + TTS",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audio content-types accepted from the browser's MediaRecorder, mapped to a
# file suffix so Whisper can correctly detect the format.
_SUFFIX_BY_CONTENT_TYPE = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
}


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class HistoryTurn(BaseModel):
    role: str
    content: str


class TextChatRequest(BaseModel):
    message: str
    history: List[HistoryTurn] = Field(default_factory=list)


class ChatResponse(BaseModel):
    transcript: Optional[str] = None
    reply: str
    audio_base64: str
    history: List[HistoryTurn]


class HealthResponse(BaseModel):
    status: str
    warnings: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Startup checks
# --------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    warnings = settings.validate()
    if warnings:
        for w in warnings:
            logger.warning("Config warning: %s", w)
    else:
        logger.info("Configuration OK. LLM=%s STT=%s TTS=%s", settings.LLM_PROVIDER, settings.STT_PROVIDER, settings.TTS_PROVIDER)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", warnings=settings.validate())


@app.post("/api/voice-chat", response_model=ChatResponse)
async def voice_chat(
    audio: UploadFile = File(..., description="Recorded audio clip (webm/wav/mp3/m4a/ogg)"),
    history: str = Form("[]", description="JSON-encoded array of prior {role, content} turns"),
):
    """
    Full voice pipeline: transcribe the uploaded audio, run the agent,
    synthesize the reply, and return everything the client needs.
    """
    # --- validate size ---
    raw = await audio.read()
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > settings.MAX_AUDIO_MB:
        raise HTTPException(status_code=413, detail=f"Audio file too large ({size_mb:.1f} MB).")
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file received.")

    # --- parse history ---
    try:
        history_list = json.loads(history) if history else []
        if not isinstance(history_list, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="`history` must be a JSON array.")

    # --- write to a temp file so the STT SDK can read it with the right suffix ---
    suffix = _SUFFIX_BY_CONTENT_TYPE.get(audio.content_type, ".webm")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name

        transcript = transcribe(tmp_path)
        if not transcript:
            raise HTTPException(status_code=422, detail="Could not detect any speech in the audio.")

        reply_text, updated_history = generate_reply(history_list, transcript)
        audio_bytes = await synthesize(reply_text)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        return ChatResponse(
            transcript=transcript,
            reply=reply_text,
            audio_base64=audio_b64,
            history=updated_history,
        )

    except TranscriptionError as exc:
        raise HTTPException(status_code=502, detail=f"Speech-to-text failed: {exc}")
    except SpeechSynthesisError as exc:
        raise HTTPException(status_code=502, detail=f"Text-to-speech failed: {exc}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in /api/voice-chat")
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/api/text-chat", response_model=ChatResponse)
async def text_chat(payload: TextChatRequest):
    """
    Text-only variant of the pipeline (no STT). Useful for testing the agent
    and TTS without a microphone, or for a typed-message fallback in the UI.
    """
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="`message` must not be empty.")

    history_list = [h.model_dump() for h in payload.history]

    try:
        reply_text, updated_history = generate_reply(history_list, payload.message)
        audio_bytes = await synthesize(reply_text)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        return ChatResponse(
            transcript=None,
            reply=reply_text,
            audio_base64=audio_b64,
            history=updated_history,
        )
    except SpeechSynthesisError as exc:
        raise HTTPException(status_code=502, detail=f"Text-to-speech failed: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error in /api/text-chat")
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)