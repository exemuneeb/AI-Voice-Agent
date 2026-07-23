# Voice AI Agent

A real-time voice assistant, inspired by tools like Superwhisper: talk to it, it transcribes
your speech with **Whisper**, thinks with an **LLM agent** (with tool calling), and speaks
its answer back using **text-to-speech**.

```
🎙️  You speak
      │
      ▼
Whisper (Groq / OpenAI)  →  transcribed text
      │
      ▼
LLM Agent (Groq / OpenAI, with tool calling)  →  reply text
      │
      ▼
Text-to-Speech (Edge TTS / ElevenLabs)  →  spoken reply
      │
      ▼
🔊  You hear the answer
```

---

## Features

- **Speech-to-Text** — Whisper via Groq (`whisper-large-v3`, fast + generous free tier) or OpenAI (`whisper-1`).
- **AI Agent** — conversational LLM (Groq or OpenAI) that keeps context across turns and can call tools
  (built-in: current time, live weather — easy to extend with your own).
- **Text-to-Speech** — converts the agent's reply into natural speech, via **Microsoft Edge TTS**
  (free, no API key, default) or **ElevenLabs** (higher quality, optional, requires a paid plan
  for API access).
- **Basic web UI** — single mic button, live transcript, typed-message fallback, deployable as a
  static site on Vercel in minutes.
- **Clean FastAPI backend** — typed request/response models, CORS, proper error handling, no
  local ML models to install (everything runs through hosted APIs).

---

## Project structure

```
voice-ai-agent/
├── backend/
│   ├── main.py            # FastAPI app & routes
│   ├── agent.py           # LLM conversation + tool-calling loop
│   ├── stt.py              # Whisper speech-to-text
│   ├── tts.py               # Text-to-speech (Edge TTS / ElevenLabs)
│   ├── tools.py              # Tool schemas + implementations
│   ├── config.py              # Environment-based settings
│   ├── requirements.txt
│   ├── Dockerfile              # For Render / Railway / Fly / any container host
│   └── .env.example
├── frontend/
│   ├── index.html          # Static UI (no build step)
│   ├── style.css
│   ├── script.js
│   └── vercel.json
└── README.md
```

---

## How it works

1. The browser records audio with `MediaRecorder` (webm) when you tap the mic.
2. On stop, the clip is POSTed to `POST /api/voice-chat` on the backend, along with the
   conversation history (kept client-side, sent each turn).
3. The backend:
   - Sends the audio to **Whisper** and gets back a transcript.
   - Sends the transcript + history to the **LLM**, which may call a **tool** (e.g. weather) before
     producing a final reply.
   - Sends the reply text to the **TTS provider** and gets back an MP3.
   - Returns `{ transcript, reply, audio_base64, history }` as JSON.
4. The frontend shows the transcript + reply as chat bubbles and plays the audio.

A typed-message fallback (`POST /api/text-chat`) is also included, useful when you don't have a
mic handy, or for quickly testing the agent/tools without recording audio.

---

## Prerequisites

- Python 3.10+
- API keys:
  - [Groq](https://console.groq.com/keys) — free tier, for LLM + Whisper STT (one key covers both)
  - **No key needed for TTS** — the default provider is Microsoft Edge TTS, which is free and
    keyless. ElevenLabs is supported as an optional alternative, but note their free tier no
    longer allows API access to voices (a paid plan is required if you want to use it).
  - Optionally an [OpenAI](https://platform.openai.com/api-keys) key if you'd rather use
    OpenAI for the LLM and/or `whisper-1` for STT

---

## 1. Backend setup (local)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows (Git Bash): source .venv/Scripts/activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and add your GROQ_API_KEY
# (TTS needs no key by default — it uses free Microsoft Edge TTS)

uvicorn main:app --reload --port 8000
```

Check it's alive:

```bash
curl http://localhost:8000/api/health
```

You should see `{"status":"ok","warnings":[]}`. If `warnings` isn't empty, it'll tell you exactly
which environment variable is missing.

### Environment variables

| Variable                | Default                      | Description                                              |
|--------------------------|-------------------------------|------------------------------------------------------------|
| `LLM_PROVIDER`           | `groq`                        | `groq` or `openai`                                          |
| `LLM_MODEL`              | `llama-3.3-70b-versatile`     | Chat model name for the chosen provider                    |
| `GROQ_API_KEY`           | —                              | Required if using Groq for LLM and/or STT                  |
| `OPENAI_API_KEY`         | —                              | Required if using OpenAI for LLM and/or STT                |
| `STT_PROVIDER`           | `groq`                        | `groq` (`whisper-large-v3`) or `openai` (`whisper-1`)       |
| `TTS_PROVIDER`           | `edge`                        | `edge` (free, no key) or `elevenlabs` (paid plan required for API access to voices) |
| `EDGE_VOICE`             | `en-US-AriaNeural`            | Any free Microsoft Edge TTS voice name (see below)          |
| `ELEVENLABS_API_KEY`     | —                              | Only needed if `TTS_PROVIDER=elevenlabs`                    |
| `ELEVENLABS_VOICE_ID`    | Rachel (`21m00Tcm4TlvDq8ikWAM`)| Any voice ID from your ElevenLabs account                  |
| `ELEVENLABS_MODEL_ID`    | `eleven_turbo_v2_5`            | ElevenLabs model                                            |
| `AGENT_NAME`             | `Aria`                        | Name the agent refers to itself as                          |
| `FRONTEND_ORIGIN`        | `*`                            | Comma-separated allowed CORS origins in production          |
| `MAX_AUDIO_MB`           | `15`                           | Max upload size for a recorded clip                        |
| `MAX_HISTORY_TURNS`      | `12`                           | How many past turns are kept in context                    |

---

## 2. Frontend setup (local)

No build step — it's plain HTML/CSS/JS.

```bash
cd frontend
python -m http.server 5500
```

Open `http://localhost:5500`. It loads straight into the mic screen and connects to
`http://localhost:8000` by default. Click the gear icon any time to change the backend URL.
Tap the mic and talk.

---

## Deployment

### Frontend → Vercel

The frontend is a static site, so it deploys to Vercel as-is, with no build step:

1. Push this repo to GitHub.
2. In Vercel: **New Project → Import** your repo.
3. Set **Root Directory** to `frontend`.
4. Framework preset: **Other** (no build command, no output directory needed).
5. Deploy.
6. Open the deployed URL, click the gear icon, and set **Backend URL** to your deployed
   backend's URL (see below).

### Backend → Render / Railway / Fly.io (recommended)

> **Why not Vercel for the backend?** Vercel's serverless/edge functions are built for short,
> stateless requests. This backend's pipeline (Whisper → LLM → TTS) can take several
> seconds, and Vercel's Python runtime doesn't handle multipart audio uploads and longer,
> variable-length function execution as cleanly as a normal long-running server. A small always-on
> Python host is simpler and more reliable for this use case, and every option below has a free tier.

**Render (simplest):**

1. New **Web Service** → connect your repo.
2. Root directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add the environment variables from the table above.
6. Deploy, then copy the resulting URL (e.g. `https://your-app.onrender.com`) into the
   frontend's Settings panel as the Backend URL, and set `FRONTEND_ORIGIN` on the backend to
   your Vercel URL (e.g. `https://your-app.vercel.app`).

**Railway / Fly.io:** same idea — point them at `backend/`, they'll pick up the `Dockerfile`
automatically. Set the same environment variables.

**Docker (any host):**

```bash
cd backend
docker build -t voice-agent-backend .
docker run -p 8000:8000 --env-file .env voice-agent-backend
```

---

## API reference

### `GET /api/health`
Returns `{ status, warnings[] }`. Use this to confirm all required API keys are configured.

### `POST /api/voice-chat`
`multipart/form-data`:
- `audio` — audio file (webm/wav/mp3/m4a/ogg)
- `history` — JSON string, array of `{ role, content }` (optional, default `[]`)

Returns:
```json
{
  "transcript": "what did you hear",
  "reply": "the agent's answer",
  "audio_base64": "…mp3 bytes, base64…",
  "history": [{ "role": "user", "content": "..." }, { "role": "assistant", "content": "..." }]
}
```

### `POST /api/text-chat`
`application/json`: `{ "message": "...", "history": [...] }` — same response shape (without
`transcript`). Useful for testing without a microphone.

---

## Changing the voice (free Edge TTS)

The default voice is `en-US-AriaNeural`. To see all available free voices:

```bash
cd backend
python -m edge_tts --list-voices
```

Pick any `ShortName` from that list (e.g. `en-GB-SoniaNeural`, `en-US-GuyNeural`) and set it in `.env`:

```
EDGE_VOICE=en-GB-SoniaNeural
```

## Adding your own tools

Open `backend/tools.py`:

1. Write a function that returns a string.
2. Add its JSON schema to `TOOL_SCHEMAS`.
3. Register it in `TOOL_IMPLEMENTATIONS`.

The agent (`agent.py`) will automatically pick it up — no other changes needed. The loop in
`generate_reply` handles the model deciding to call a tool, executing it, and feeding the result
back for a final natural-language answer.

---

## Troubleshooting

- **"Backend unreachable"** in the UI → check the Backend URL in Settings, and that the backend's
  `/api/health` responds from your browser.
- **CORS errors in the browser console** → set `FRONTEND_ORIGIN` on the backend to your exact
  Vercel URL (no trailing slash), and redeploy.
- **No sound plays** → some browsers block autoplay; the app requests playback right after your
  own tap on the mic button, which should satisfy autoplay policies. Try clicking anywhere on the
  page first if it's still silent.
- **"Could not detect any speech"** → check mic permissions, and make sure you're not recording
  extreme silence (very short taps produce empty clips).
- **422/502 errors** → almost always a missing or invalid API key; check `/api/health` for
  specific warnings.
- **ElevenLabs 402 "payment_required"** → their free tier no longer allows API access to
  library voices. Either switch back to `TTS_PROVIDER=edge` (free, default), or upgrade your
  ElevenLabs plan.

---

## Notes & possible extensions

- Swap `LLM_PROVIDER`/`STT_PROVIDER` between `groq` and `openai` independently via env vars —
  the code path is identical for both since they share an OpenAI-compatible API shape.
- Swap `TTS_PROVIDER` between `edge` and `elevenlabs` the same way.
- To add Gemini, add a third branch in `agent.py`'s `_get_client()` using the `google-genai` SDK
  (its interface differs slightly from the OpenAI SDK, so the calling code would need a small
  adapter).
- For true low-latency streaming (partial transcripts while still speaking, token-by-token TTS),
  you'd move from this request/response model to WebSockets with streaming STT/TTS APIs — a
  good next step once the basic pipeline above is working end-to-end.

---

## License

MIT — do whatever you'd like with this.
