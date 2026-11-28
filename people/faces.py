"""Offline face enrollment + recognition (dlib ResNet via ``face_recognition``).

Runs entirely on this machine's CPU: no image or face data ever leaves it. Only
people enrolled on the dashboard's People tab can be recognized.

Distances are dlib's 128-d embedding distances; same person is typically < 0.5.
``MATCH_DISTANCE`` is deliberately stricter than the library default (0.6) so a
stranger is called "someone I don't recognize" rather than mis-named.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np

MATCH_DISTANCE = 0.5
MAX_SIDE = 1600
JPEG_QUALITY = 90


class PhotoError(ValueError):
    """The upload is not a usable image."""


@dataclass(frozen=True)
class FaceMatch:
    person_id: str | None
    name: str | None
    distance: float

    @property
    def confidence(self) -> float:
        """0..1, 1 = identical embedding; ~0.5+ for a solid match."""
        return round(max(0.0, 1.0 - self.distance), 2)


_MODELS = None


def _models():
    """dlib HOG detector + 68-point landmarks + ResNet face encoder (loaded once).

    Same models and calls as the ``face_recognition`` package, used directly so the
    install is just the prebuilt ``dlib-bin`` wheel + ``face_recognition_models``.
    """
    global _MODELS
    if _MODELS is None:
        import dlib  # noqa: PLC0415

        with warnings.catch_warnings():  # face_recognition_models imports pkg_resources
            warnings.simplefilter("ignore")
            import face_recognition_models as frm  # noqa: PLC0415
        _MODELS = (
            dlib.get_frontal_face_detector(),
            dlib.shape_predictor(frm.pose_predictor_model_location()),
            dlib.face_recognition_model_v1(frm.face_recognition_model_location()),
        )
    return _MODELS


def decode_image(data: bytes) -> np.ndarray:
    """Bytes -> RGB array (EXIF orientation applied), or ``PhotoError``."""
    import cv2  # noqa: PLC0415

    if not data:
        raise PhotoError("Empty file.")
    bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise PhotoError("Not an image JARVIS can read (use JPG, PNG or WebP).")
    height, width = bgr.shape[:2]
    if max(height, width) > MAX_SIDE:
        scale = MAX_SIDE / max(height, width)
        bgr = cv2.resize(bgr, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(bgr[:, :, ::-1])


def encode_jpeg(rgb: np.ndarray) -> bytes:
    import cv2  # noqa: PLC0415

    ok, buf = cv2.imencode(".jpg", rgb[:, :, ::-1], [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        raise PhotoError("Could not re-encode the image.")
    return buf.tobytes()


def face_encodings(rgb: np.ndarray, upsample: int = 1) -> list[tuple[tuple[int, int, int, int], np.ndarray]]:
    """``[(box, encoding)]`` for every face found, largest face first. Box = (top, right, bottom, left)."""
    detector, landmarks, encoder = _models()
    rects = sorted(detector(rgb, upsample), key=lambda r: r.width() * r.height(), reverse=True)
    results = []
    for rect in rects:
        shape = landmarks(rgb, rect)
        encoding = np.array(encoder.compute_face_descriptor(rgb, shape, 1))
        box = (max(rect.top(), 0), min(rect.right(), rgb.shape[1]), min(rect.bottom(), rgb.shape[0]), max(rect.left(), 0))
        results.append((box, encoding))
    return results


def prepare_photo(data: bytes) -> tuple[bytes, np.ndarray | None]:
    """Validate an uploaded photo; return (clean JPEG without metadata, largest-face encoding or None)."""
    rgb = decode_image(data)
    faces = face_encodings(rgb)
    return encode_jpeg(rgb), (faces[0][1] if faces else None)


def recognize(rgb: np.ndarray, known: list[tuple[str, str, np.ndarray]]) -> list[FaceMatch]:
    """One ``FaceMatch`` per face in ``rgb``: the closest enrolled person within
    ``MATCH_DISTANCE``, or an unknown match (name ``None``)."""
    results: list[FaceMatch] = []
    known_matrix = np.stack([k[2] for k in known]) if known else None
    for _box, encoding in face_encodings(rgb):
        if known_matrix is None:
            results.append(FaceMatch(None, None, 1.0))
            continue
        distances = np.linalg.norm(known_matrix - encoding, axis=1)
        best = int(np.argmin(distances))
        distance = float(distances[best])
        if distance <= MATCH_DISTANCE:
            results.append(FaceMatch(known[best][0], known[best][1], distance))
        else:
            results.append(FaceMatch(None, None, distance))
    return results


def describe_faces(matches: list[FaceMatch]) -> str | None:
    """One spoken-friendly sentence for the brain, or None when nobody is in view."""
    if not matches:
        return None
    named: dict[str, FaceMatch] = {}
    for m in matches:
        if m.name and (m.name not in named or m.distance < named[m.name].distance):
            named[m.name] = m
    unknown = sum(1 for m in matches if m.name is None)
    parts = [f"I see {m.name} (confidence {m.confidence:.2f})" for m in named.values()]
    if unknown:
        parts.append("someone I don't recognize" if unknown == 1 else f"{unknown} people I don't recognize")
    sentence = " and ".join(parts)
    return sentence[0].upper() + sentence[1:] + "."
