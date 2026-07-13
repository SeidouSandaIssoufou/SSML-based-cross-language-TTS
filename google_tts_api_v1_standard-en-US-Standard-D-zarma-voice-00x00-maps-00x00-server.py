#### CREATES A SERVER THAT YOU CAN USE TO MAKE GOOGLE SPEECH ENGINE TALK USING SSML - YOU CAN INOVKE THE SERVER USING VBA

import os
import uuid
import ctypes
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
from google.cloud import texttospeech

# =============================
# CONFIG
# =============================
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"my-iss-test-project-153a6bdb683e.json"

AUDIO_DIR = Path("audio_preview")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_LANGUAGE_CODE = "en-US"
DEFAULT_VOICE_NAME = "en-US-Standard-D"
DEFAULT_SPEAKING_RATE = 1.0
DEFAULT_VOLUME_GAIN_DB = 0.0
DEFAULT_PITCH = 0.0

app = FastAPI(title="Local Google TTS API", version="1.0")


# =============================
# WINDOWS PLAYBACK (NO FFMPEG)
# =============================
def mci(cmd: str) -> str:
    buf = ctypes.create_unicode_buffer(255)
    ctypes.windll.winmm.mciSendStringW(cmd, buf, 254, None)
    return buf.value


def play_audio_blocking(file_path: str):
    file_path = str(Path(file_path).resolve())
    alias = f"sound_{uuid.uuid4().hex}"

    mci(f'open "{file_path}" alias {alias}')
    mci(f'play {alias}')

    while True:
        status = mci(f"status {alias} mode")
        if status.lower() != "playing":
            break
        time.sleep(0.05)

    mci(f"close {alias}")


# =============================
# GOOGLE TTS: SSML SYNTHESIS
# =============================
def synthesize_ssml_to_mp3(
    ssml: str,
    out_path: str,
    language_code: str = DEFAULT_LANGUAGE_CODE,
    voice_name: str = DEFAULT_VOICE_NAME,
    speaking_rate: float = DEFAULT_SPEAKING_RATE,
    volume_gain_db: float = DEFAULT_VOLUME_GAIN_DB,
    pitch: float = DEFAULT_PITCH,
):
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(ssml=ssml)
    voice = texttospeech.VoiceSelectionParams(language_code=language_code, name=voice_name)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speaking_rate,
        volume_gain_db=volume_gain_db,
        pitch=pitch,
    )

    response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(response.audio_content)
    return out_file


# =============================
# REQUEST MODEL (SSML)
# =============================
class TTS_SSML_Request(BaseModel):
    ssml: str
    language_code: Optional[str] = DEFAULT_LANGUAGE_CODE
    voice_name: Optional[str] = DEFAULT_VOICE_NAME
    speaking_rate: Optional[float] = DEFAULT_SPEAKING_RATE
    volume_gain_db: Optional[float] = DEFAULT_VOLUME_GAIN_DB
    pitch: Optional[float] = DEFAULT_PITCH
    play: Optional[bool] = True
    filename: Optional[str] = None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/tts_ssml")
def tts_ssml(req: TTS_SSML_Request):
    ssml = (req.ssml or "").strip()

    if not ssml:
        return {"ok": False, "error": "SSML is empty"}

    if not ssml.startswith("<speak"):
        return {"ok": False, "error": "SSML must start with <speak>...</speak>"}

    name = req.filename.strip() if req.filename else uuid.uuid4().hex
    out_path = AUDIO_DIR / f"{name}.mp3"

    try:
        out_file = synthesize_ssml_to_mp3(
            ssml=ssml,
            out_path=str(out_path),
            language_code=req.language_code,
            voice_name=req.voice_name,
            speaking_rate=req.speaking_rate,
            volume_gain_db=req.volume_gain_db,
            pitch=req.pitch,
        )
    except Exception as e:
        return {"ok": False, "error": f"TTS failed: {e}"}

    if req.play:
        try:
            play_audio_blocking(str(out_file))
        except Exception as e:
            return {"ok": False, "error": f"Playback failed: {e}", "file": str(out_file)}

    return {"ok": True, "file": str(out_file), "played": bool(req.play)}
