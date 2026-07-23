"""
Centralized configuration for the Voice AI Agent backend.
All values are loaded from environment variables (see .env.example).
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # --- LLM (the "brain" of the agent) ---
    # Provider can be "groq" (fast + free tier, recommended) or "openai".
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").lower()
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # --- Speech-to-Text (Whisper) ---
    # Provider can be "groq" (hosted whisper-large-v3, very fast) or "openai" (whisper-1).
    STT_PROVIDER: str = os.getenv("STT_PROVIDER", "groq").lower()
    STT_MODEL_GROQ: str = os.getenv("STT_MODEL_GROQ", "whisper-large-v3")
    STT_MODEL_OPENAI: str = os.getenv("STT_MODEL_OPENAI", "whisper-1")

    # --- Text-to-Speech ---
    # Provider can be "edge" (free, no API key, via Microsoft Edge TTS) or
    # "elevenlabs" (higher quality, but requires a paid plan to use voices via API).
    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "edge").lower()

    # Microsoft Edge TTS (free, no key required)
    EDGE_VOICE: str = os.getenv("EDGE_VOICE", "en-US-AriaNeural")

    # ElevenLabs (optional, paid plan required for API access to voices)
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    ELEVENLABS_MODEL_ID: str = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
    ELEVENLABS_OUTPUT_FORMAT: str = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128")

    # --- App / server ---
    AGENT_NAME: str = os.getenv("AGENT_NAME", "Aria")
    # Comma separated list of allowed origins for CORS, or "*" for any.
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "*")
    MAX_AUDIO_MB: int = int(os.getenv("MAX_AUDIO_MB", "15"))
    MAX_HISTORY_TURNS: int = int(os.getenv("MAX_HISTORY_TURNS", "12"))
    PORT: int = int(os.getenv("PORT", "8000"))

    @property
    def cors_origins(self):
        if self.FRONTEND_ORIGIN.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.FRONTEND_ORIGIN.split(",") if o.strip()]

    def validate(self) -> list:
        """Returns a list of human-readable warnings for missing/likely-broken config."""
        warnings = []

        if self.LLM_PROVIDER == "groq" and not self.GROQ_API_KEY:
            warnings.append("GROQ_API_KEY is not set but LLM_PROVIDER=groq.")
        if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            warnings.append("OPENAI_API_KEY is not set but LLM_PROVIDER=openai.")
        if self.LLM_PROVIDER not in ("groq", "openai"):
            warnings.append(f"Unknown LLM_PROVIDER '{self.LLM_PROVIDER}'. Use 'groq' or 'openai'.")

        if self.STT_PROVIDER == "groq" and not self.GROQ_API_KEY:
            warnings.append("GROQ_API_KEY is not set but STT_PROVIDER=groq.")
        if self.STT_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            warnings.append("OPENAI_API_KEY is not set but STT_PROVIDER=openai.")
        if self.STT_PROVIDER not in ("groq", "openai"):
            warnings.append(f"Unknown STT_PROVIDER '{self.STT_PROVIDER}'. Use 'groq' or 'openai'.")

        if self.TTS_PROVIDER == "elevenlabs" and not self.ELEVENLABS_API_KEY:
            warnings.append("ELEVENLABS_API_KEY is not set but TTS_PROVIDER=elevenlabs.")
        if self.TTS_PROVIDER not in ("edge", "elevenlabs"):
            warnings.append(f"Unknown TTS_PROVIDER '{self.TTS_PROVIDER}'. Use 'edge' or 'elevenlabs'.")

        return warnings


settings = Settings()
