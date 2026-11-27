"""People JARVIS knows: profiles + photos, stored locally only.

* SQLite (``people.db``) + a ``photos/`` folder under the JARVIS data dir
  (``%LOCALAPPDATA%\\JARVIS\\people`` by default, ``JARVIS_DATA_DIR`` to move it).
  Nothing here is ever uploaded anywhere.
* Every person is mirrored to the Obsidian vault as ``JARVIS/People/<Name>.md`` so
  the brain (and Bill) can read the profile as a normal note.
* Deleting a person is a soft delete (``deleted_at``): the row and photos stay
  on disk, the person disappears from lists, lookups, recognition and the vault.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PROFILE_FIELDS = ("name", "relationship", "company", "role", "phone", "email", "notes")
SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    relationship TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    facts TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_people_name ON people(name);
CREATE TABLE IF NOT EXISTS photos (
    id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL REFERENCES people(id),
    filename TEXT NOT NULL,
    encoding BLOB,
    has_face INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_photos_person ON photos(person_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_data_dir() -> Path:
    base = os.getenv("JARVIS_DATA_DIR") or os.path.join(os.getenv("LOCALAPPDATA", str(Path.home())), "JARVIS")
    return Path(base) / "people"


@dataclass(frozen=True)
class Photo:
    id: str
    person_id: str
    has_face: bool
    created_at: str


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    relationship: str = ""
    company: str = ""
    role: str = ""
    phone: str = ""
    email: str = ""
    notes: str = ""
    facts: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    photos: list[Photo] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def one_line(self) -> str:
        work = " ".join(x for x in (self.role, f"at {self.company}" if self.company else "") if x)
        bits = [b for b in (self.relationship, work) if b]
        return f"{self.name} ({', '.join(bits)})" if bits else self.name


class PeopleStore:
    def __init__(self, data_dir: Path | None = None, vault: Path | None = None) -> None:
        self.dir = Path(data_dir) if data_dir else default_data_dir()
        self.photos_dir = self.dir / "photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.vault = Path(vault) if vault else None
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.dir / "people.db", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # ---- reading --------------------------------------------------------
    def _photos(self, person_id: str) -> list[Photo]:
        rows = self._db.execute(
            "SELECT id, person_id, has_face, created_at FROM photos"
            " WHERE person_id=? AND deleted_at IS NULL ORDER BY created_at",
            (person_id,),
        ).fetchall()
        return [Photo(r["id"], r["person_id"], bool(r["has_face"]), r["created_at"]) for r in rows]

    def _person(self, row: sqlite3.Row) -> Person:
        return Person(
            id=row["id"], name=row["name"], relationship=row["relationship"], company=row["company"],
            role=row["role"], phone=row["phone"], email=row["email"], notes=row["notes"],
            facts=json.loads(row["facts"] or "[]"), created_at=row["created_at"], updated_at=row["updated_at"],
            photos=self._photos(row["id"]),
        )

    def list(self, query: str = "") -> list[Person]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM people WHERE deleted_at IS NULL ORDER BY name COLLATE NOCASE"
            ).fetchall()
            people = [self._person(r) for r in rows]
        q = query.strip().lower()
        if not q:
            return people
        return [p for p in people if q in " ".join([*(getattr(p, f) for f in PROFILE_FIELDS), *p.facts]).lower()]

    def get(self, person_id: str) -> Person:
        with self._lock:
            row = self._db.execute("SELECT * FROM people WHERE id=? AND deleted_at IS NULL", (person_id,)).fetchone()
            if row is None:
                raise KeyError(person_id)
            return self._person(row)

    def find(self, name: str) -> list[Person]:
        """People whose name matches ``name`` (exact first, then first-name / partial)."""
        wanted = name.strip().lower()
        if not wanted:
            return []
        people = self.list()
        exact = [p for p in people if p.name.lower() == wanted]
        if exact:
            return exact
        tokens = set(wanted.split())
        return [p for p in people if wanted in p.name.lower() or tokens & set(p.name.lower().split())]

    # ---- writing --------------------------------------------------------
    def create(self, fields: dict) -> Person:
        name = (fields.get("name") or "").strip()
        if not name:
            raise ValueError("A person needs a name.")
        person_id = uuid.uuid4().hex
        now = _now()
        values = {f: (fields.get(f) or "").strip() for f in PROFILE_FIELDS}
        with self._lock:
            self._db.execute(
                "INSERT INTO people (id, name, relationship, company, role, phone, email, notes, facts,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (person_id, values["name"], values["relationship"], values["company"], values["role"],
                 values["phone"], values["email"], values["notes"], json.dumps(_clean_facts(fields.get("facts"))),
                 now, now),
            )
            self._db.commit()
        person = self.get(person_id)
        self._mirror(person)
        return person

    def update(self, person_id: str, fields: dict) -> Person:
        before = self.get(person_id)
        values = {f: (fields[f] or "").strip() if f in fields else getattr(before, f) for f in PROFILE_FIELDS}
        if not values["name"]:
            raise ValueError("A person needs a name.")
        facts = _clean_facts(fields["facts"]) if "facts" in fields else before.facts
        with self._lock:
            self._db.execute(
                "UPDATE people SET name=?, relationship=?, company=?, role=?, phone=?, email=?, notes=?, facts=?,"
                " updated_at=? WHERE id=? AND deleted_at IS NULL",
                (values["name"], values["relationship"], values["company"], values["role"], values["phone"],
                 values["email"], values["notes"], json.dumps(facts), _now(), person_id),
            )
            self._db.commit()
        person = self.get(person_id)
        if before.name != person.name:
            self._unmirror(before.name)
        self._mirror(person)
        return person

    def delete(self, person_id: str) -> None:
        person = self.get(person_id)
        now = _now()
        with self._lock:
            self._db.execute("UPDATE people SET deleted_at=? WHERE id=?", (now, person_id))
            self._db.execute(
                "UPDATE photos SET deleted_at=? WHERE person_id=? AND deleted_at IS NULL", (now, person_id)
            )
            self._db.commit()
        self._unmirror(person.name)

    # ---- photos ---------------------------------------------------------
    def add_photo(self, person_id: str, jpeg: bytes, encoding: np.ndarray | None) -> Photo:
        """Store a (re-encoded, metadata-free) JPEG and its face encoding, if any."""
        self.get(person_id)  # must exist
        photo_id = uuid.uuid4().hex
        filename = f"{person_id}-{photo_id}.jpg"
        (self.photos_dir / filename).write_bytes(jpeg)
        blob = encoding.astype(np.float64).tobytes() if encoding is not None else None
        created = _now()
        with self._lock:
            self._db.execute(
                "INSERT INTO photos (id, person_id, filename, encoding, has_face, created_at) VALUES (?,?,?,?,?,?)",
                (photo_id, person_id, filename, blob, int(encoding is not None), created),
            )
            self._db.commit()
        self._mirror(self.get(person_id))
        return Photo(photo_id, person_id, encoding is not None, created)

    def photo_path(self, person_id: str, photo_id: str) -> Path:
        with self._lock:
            row = self._db.execute(
                "SELECT filename FROM photos WHERE id=? AND person_id=? AND deleted_at IS NULL",
                (photo_id, person_id),
            ).fetchone()
        if row is None:
            raise KeyError(photo_id)
        return self.photos_dir / row["filename"]

    def delete_photo(self, person_id: str, photo_id: str) -> None:
        self.photo_path(person_id, photo_id)  # must exist
        with self._lock:
            self._db.execute(
                "UPDATE photos SET deleted_at=? WHERE id=? AND person_id=?", (_now(), photo_id, person_id)
            )
            self._db.commit()
        self._mirror(self.get(person_id))

    def encodings(self) -> list[tuple[str, str, np.ndarray]]:
        """``(person_id, name, encoding)`` for every enrolled face of a live person."""
        with self._lock:
            rows = self._db.execute(
                "SELECT p.id, p.name, ph.encoding FROM photos ph JOIN people p ON p.id = ph.person_id"
                " WHERE ph.deleted_at IS NULL AND p.deleted_at IS NULL AND ph.encoding IS NOT NULL"
            ).fetchall()
        return [(r["id"], r["name"], np.frombuffer(r["encoding"], dtype=np.float64)) for r in rows]

    # ---- Obsidian mirror -----------------------------------------------
    def _note_path(self, name: str) -> Path | None:
        if self.vault is None:
            return None
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip().rstrip(".") or "Unnamed"
        return self.vault / "JARVIS" / "People" / f"{safe}.md"

    def _mirror(self, person: Person) -> None:
        path = self._note_path(person.name)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "---", "type: person", f"jarvis_person_id: {person.id}", f"updated_at: {person.updated_at}", "---", "",
            f"# {person.name}", "",
        ]
        for label, value in (("Relationship", person.relationship), ("Company", person.company),
                             ("Role", person.role), ("Phone", person.phone), ("Email", person.email)):
            if value:
                lines.append(f"- **{label}:** {value}")
        if person.notes:
            lines += ["", "## Notes", "", person.notes]
        if person.facts:
            lines += ["", "## Facts", "", *(f"- {fact}" for fact in person.facts)]
        lines += ["", f"_{len(person.photos)} photo(s) enrolled for recognition (stored locally by JARVIS)._", ""]
        path.write_text("\n".join(lines), encoding="utf-8")

    def _unmirror(self, name: str) -> None:
        path = self._note_path(name)
        if path is not None and path.exists():
            path.unlink()


def _clean_facts(facts) -> list[str]:
    if not facts:
        return []
    if isinstance(facts, str):
        facts = facts.splitlines()
    return [str(f).strip() for f in facts if str(f).strip()][:100]
