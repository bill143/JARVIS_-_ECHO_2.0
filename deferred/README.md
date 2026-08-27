# /deferred — quarantined, out-of-scope code

Code here is **intentionally not shipped**. It is parked because the current
phase scope excludes it. Nothing in the shipped JARVIS modules imports from this
folder, and CI does not wire it into the app.

## vision.py — webcam vision tool (DEFERRED)

JARVIS is **voice-only** for this phase (scope lock). The webcam vision tool —
the `see` function, OpenCV desktop capture, and the WebRTC video-track path —
lives here until vision is formally back in scope.

To bring it back: move `vision.py` to the repo root, re-add the tool
registration in `assistant.py` / `assistant_web.py`, set `video_in_enabled=True`
on the WebRTC transport, and restore `opencv-python` to `requirements.txt`.
