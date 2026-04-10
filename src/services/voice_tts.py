"""ElevenLabs TTS service — converts text to MP3 and saves to /app/tmp/audio/."""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx

AUDIO_DIR = Path("/app/tmp/audio")
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
# Streaming endpoint for lower latency (returns chunks as they generate)
ELEVENLABS_STREAM_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"


def _audio_dir() -> Path:
    d = AUDIO_DIR if AUDIO_DIR.exists() else Path("/tmp/hostai_audio")
    d.mkdir(parents=True, exist_ok=True)
    return d


def synthesize(text: str, api_key: str, voice_id: str) -> str:
    """
    Call ElevenLabs streaming API, save MP3, return the file UUID.
    Uses turbo v2.5 model for lower latency + streaming for faster first byte.
    """
    url = ELEVENLABS_STREAM_URL.format(voice_id=voice_id)
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.3,
            "similarity_boost": 0.85,
            "style": 0.4,
            "use_speaker_boost": True,
        },
        "optimize_streaming_latency": 3,
    }

    uid = str(uuid.uuid4())
    out_path = _audio_dir() / f"{uid}.mp3"

    # Stream response to disk — first bytes arrive much faster than full generation
    with httpx.stream("POST", url, json=payload, headers=headers, timeout=30) as response:
        response.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)

    return uid


def get_audio_path(uid: str) -> Path | None:
    for base in (AUDIO_DIR, Path("/tmp/hostai_audio")):
        p = base / f"{uid}.mp3"
        if p.exists():
            return p
    return None
