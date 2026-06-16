# JARVIS & ECHO 2.0 — self-contained container (browser / WebRTC build).
#
# Bundles the whole local voice stack (Whisper + Kokoro + Silero). The model
# files download on first run and are cached in /models (mount a volume so they
# persist — see docker-compose.yml). Only the Claude API call leaves the box.
FROM python:3.11-slim

# System libs:
#  - libgl1 / libglib2.0-0  -> OpenCV (desktop vision import)
#  - libsndfile1            -> audio I/O for the TTS/STT stack
#  - ffmpeg                 -> Whisper audio decoding
#  - portaudio19-dev        -> builds pyaudio (Pipecat [local] extra)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsndfile1 \
        ffmpeg \
        portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache the model downloads on a writable, mountable path.
ENV HF_HOME=/models \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# The Pipecat dev runner serves the browser client on 7860.
EXPOSE 7860

CMD ["python", "assistant_web.py", "--host", "0.0.0.0", "--port", "7860"]
