"""List audio input devices and show which one actually hears you.

Run it, keep talking out loud until it finishes, and read the `level` column:
a silent/unused mic reads ~0-100; the mic that hears you reads several hundred+.
Then set that index as AUDIO_INPUT_DEVICE_INDEX in your .env so assistant.py
opens the right microphone.

    python mic_test.py
"""

from __future__ import annotations

import struct


def _rms(data: bytes) -> int:
    count = len(data) // 2
    if count == 0:
        return 0
    samples = struct.unpack(f"{count}h", data)
    return int((sum(s * s for s in samples) / count) ** 0.5)


def main() -> None:
    try:
        import pyaudio
    except ImportError:
        print("pyaudio is not installed. Install with: pip install -r requirements.txt")
        return

    pa = pyaudio.PyAudio()
    rate, chunk, seconds = 16000, 1024, 2
    try:
        di = pa.get_default_input_device_info()
        print(f"DEFAULT INPUT: {di['index']} {di['name']}")
    except Exception as exc:
        print(f"no default input device: {exc}")

    print("--- KEEP TALKING OUT LOUD until this finishes ---")
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) < 1:
            continue
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                input_device_index=i,
                frames_per_buffer=chunk,
            )
        except Exception:
            print(f"[{i}] {info['name']} -> cannot open")
            continue
        peak = 0
        for _ in range(int(rate / chunk * seconds)):
            try:
                peak = max(peak, _rms(stream.read(chunk, exception_on_overflow=False)))
            except Exception:
                break
        stream.close()
        print(f"[{i}] {info['name']} -> level {peak}")
    pa.terminate()


if __name__ == "__main__":
    main()
