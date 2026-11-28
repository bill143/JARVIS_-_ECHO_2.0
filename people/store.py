"""People JARVIS knows: profiles + photos, stored locally only.

* SQLite (``people.db``) + a ``photos/`` folder under the JARVIS data dir
  (``%USERPROFILE%\\JARVIS\\people`` by default, ``JARVIS_DATA_DIR`` to move it).
  Nothing here is ever uploaded anywhere.
* Every person is mirrored to the Obsidian vault as ``JARVIS/People/<Name>.md`` so
  the brain (and Bill) can read the profile as a normal note.
* Deleting a person is a soft delete (``deleted_at``): the row and photos stay
  on disk, the person disappears from lists, lookups, recognition and the vault.
* Groups (Coworkers, Friends, Family, Rugby, or any Bill adds) are headings a
  person can belong to several of. Deleting a group never deletes its people.
  They are mirrored as tags on the vault notes.
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
CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS person_groups (
    person_id TEXT NOT NULL REFERENCES people(id),
    group_id TEXT NOT NULL REFERENCES groups(id),
    added_at TEXT NOT NULL,
    PRIMARY KEY (person_id, group_id)
);
CREATE INDEX IF NOT EXISTS idx_person_groups_group ON person_groups(group_id);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
DEFAULT_GROUPS = ("Coworkers", "Friends", "Family", "Rugby")
MAX_GROUP_NAME = 60
GROUPS_SEEDED = "groups_seeded"
# Relationship words that file an existing person under a seeded group.
_GROUP_HINTS = {
    "Coworkers": ("cowork", "co-work", "colleague", "staff", "employee", "estimator", "foreman", "superintendent"),
    "Friends": ("friend", "buddy"),
    "Family": ("family", "wife", "husband", "spouse", "son", "daughter", "mother", "father", "mom", "dad",
               "brother", "sister", "cousin", "uncle", "aunt", "niece", "nephew", "grand", "in-law"),
    "Rugby": ("rugby", "teammate"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_data_dir() -> Path:
    # Not %LOCALAPPDATA%: when JARVIS is started from a packaged (MSIX) app such as
    # the Claude desktop app, Windows silently redirects AppData writes into that
    # app's private folder, so the data was invisible in File Explorer and missing
    # when JARVIS was started from its own shortcut. The user profile is not redirected.
    base = os.getenv("JARVIS_DATA_DIR") or str(Path.home() / "JARVIS")
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
    groups: list[str] = field(default_factory=list)  # group ids

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
        self._seed_groups()

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

    def _group_ids(self, person_id: str) -> list[str]:
        rows = self._db.execute(
            "SELECT g.id FROM person_groups pg JOIN groups g ON g.id = pg.group_id"
            " WHERE pg.person_id=? AND g.deleted_at IS NULL ORDER BY g.name COLLATE NOCASE",
            (person_id,),
        ).fetchall()
        return [r["id"] for r in rows]

    def _person(self, row: sqlite3.Row) -> Person:
        return Person(
            id=row["id"], name=row["name"], relationship=row["relationship"], company=row["company"],
            role=row["role"], phone=row["phone"], email=row["email"], notes=row["notes"],
            facts=json.loads(row["facts"] or "[]"), created_at=row["created_at"], updated_at=row["updated_at"],
            photos=self._photos(row["id"]), groups=self._group_ids(row["id"]),
        )

    def list(self, query: str = "", group_id: str = "") -> list[Person]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM people WHERE deleted_at IS NULL ORDER BY name COLLATE NOCASE"
            ).fetchall()
            people = [self._person(r) for r in rows]
        if group_id:
            people = [p for p in people if group_id in p.groups]
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
        groups = fields.get("groups")
        if groups is None:  # not chosen: file by Relationship (e.g. "Coworker" -> Coworkers)
            groups = self._groups_for_relationship(values["relationship"])
        if groups:
            self.set_person_groups(person_id, groups, mirror=False)
        person = self.get(person_id)
        self._mirror(person)
        return person

    def update(self, person_id: str, fields: dict) -> Person:
        before = self.get(person_id)
        values = {f: (fields[f] or "").strip() if f in fields else getattr(before, f) for f in PROFILE_FIELDS}
        if not values["name"]:
            raise ValueError("A person needs a name.")
        facts = _clean_facts(fields["facts"]) if "facts" in fields else before.facts
        if fields.get("groups") is not None:
            self.set_person_groups(person_id, fields["groups"], mirror=False)
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

    # ---- groups ---------------------------------------------------------
    def _seed_groups(self) -> None:
        """One-time migration: create the default groups and file existing people by Relationship."""
        with self._lock:
            if self._db.execute("SELECT 1 FROM meta WHERE key=?", (GROUPS_SEEDED,)).fetchone():
                return
            now = _now()
            ids = {}
            for name in DEFAULT_GROUPS:
                existing = self._db.execute(
                    "SELECT id FROM groups WHERE name=? COLLATE NOCASE AND deleted_at IS NULL", (name,)).fetchone()
                ids[name] = existing["id"] if existing else uuid.uuid4().hex
                if not existing:
                    self._db.execute("INSERT INTO groups (id, name, created_at) VALUES (?,?,?)", (ids[name], name, now))
            for row in self._db.execute("SELECT id, relationship FROM people WHERE deleted_at IS NULL").fetchall():
                rel = (row["relationship"] or "").lower()
                for name, hints in _GROUP_HINTS.items():
                    if any(h in rel for h in hints):
                        self._db.execute(
                            "INSERT OR IGNORE INTO person_groups (person_id, group_id, added_at) VALUES (?,?,?)",
                            (row["id"], ids[name], now))
            self._db.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (GROUPS_SEEDED, now))
            self._db.commit()
        if self.vault is not None:
            for person in self.list():
                self._mirror(person)

    def _groups_for_relationship(self, relationship: str) -> list[str]:
        rel = (relationship or "").lower()
        if not rel:
            return []
        by_name = {g["name"].lower(): g["id"] for g in self.groups()}
        return [by_name[name.lower()] for name, hints in _GROUP_HINTS.items()
                if name.lower() in by_name and any(h in rel for h in hints)]

    def groups(self) -> list[dict]:
        """``[{id, name, count}]`` of live groups, alphabetical; count = live people in it."""
        with self._lock:
            rows = self._db.execute(
                "SELECT g.id, g.name, COUNT(p.id) AS n FROM groups g"
                " LEFT JOIN person_groups pg ON pg.group_id = g.id"
                " LEFT JOIN people p ON p.id = pg.person_id AND p.deleted_at IS NULL"
                " WHERE g.deleted_at IS NULL GROUP BY g.id ORDER BY g.name COLLATE NOCASE"
            ).fetchall()
        return [{"id": r["id"], "name": r["name"], "count": r["n"]} for r in rows]

    def _clean_group_name(self, name: str, exclude_id: str = "") -> str:
        clean = " ".join((name or "").split())
        if not clean:
            raise ValueError("A group needs a name.")
        if len(clean) > MAX_GROUP_NAME:
            raise ValueError(f"Group names are at most {MAX_GROUP_NAME} characters.")
        clash = self._db.execute(
            "SELECT id FROM groups WHERE name=? COLLATE NOCASE AND deleted_at IS NULL AND id<>?",
            (clean, exclude_id)).fetchone()
        if clash:
            raise ValueError(f"There is already a group called {clean}.")
        return clean

    def create_group(self, name: str) -> dict:
        with self._lock:
            clean = self._clean_group_name(name)
            group_id = uuid.uuid4().hex
            self._db.execute("INSERT INTO groups (id, name, created_at) VALUES (?,?,?)", (group_id, clean, _now()))
            self._db.commit()
        return {"id": group_id, "name": clean, "count": 0}

    def _live_group(self, group_id: str) -> None:
        if not self._db.execute("SELECT 1 FROM groups WHERE id=? AND deleted_at IS NULL", (group_id,)).fetchone():
            raise KeyError(group_id)

    def _members(self, group_id: str) -> list[str]:
        return [r["person_id"] for r in self._db.execute(
            "SELECT person_id FROM person_groups WHERE group_id=?", (group_id,)).fetchall()]

    def rename_group(self, group_id: str, name: str) -> dict:
        with self._lock:
            self._live_group(group_id)
            clean = self._clean_group_name(name, exclude_id=group_id)
            self._db.execute("UPDATE groups SET name=? WHERE id=?", (clean, group_id))
            self._db.commit()
            members = self._members(group_id)
        self._remirror(members)
        return next(g for g in self.groups() if g["id"] == group_id)

    def delete_group(self, group_id: str) -> None:
        """Soft-delete the heading; its people stay (they just lose this group)."""
        with self._lock:
            self._live_group(group_id)
            members = self._members(group_id)
            self._db.execute("UPDATE groups SET deleted_at=? WHERE id=?", (_now(), group_id))
            self._db.commit()
        self._remirror(members)

    def set_person_groups(self, person_id: str, group_ids, mirror: bool = True) -> None:
        """Make the person a member of exactly ``group_ids`` (live groups only)."""
        wanted = list(dict.fromkeys(str(g) for g in (group_ids or [])))
        with self._lock:
            self.get(person_id)  # must exist
            for gid in wanted:
                self._live_group(gid)
            for gid in {g["id"] for g in self.groups()} - set(wanted):
                self._db.execute("DELETE FROM person_groups WHERE person_id=? AND group_id=?", (person_id, gid))
            now = _now()
            self._db.executemany(
                "INSERT OR IGNORE INTO person_groups (person_id, group_id, added_at) VALUES (?,?,?)",
                [(person_id, gid, now) for gid in wanted])
            self._db.commit()
        if mirror:
            self._remirror([person_id])

    def add_to_group(self, group_id: str, person_ids) -> int:
        """Add several people to one group (bulk). Returns how many were newly added."""
        ids = list(dict.fromkeys(str(p) for p in (person_ids or [])))
        with self._lock:
            self._live_group(group_id)
            for pid in ids:
                self.get(pid)
            before = len(self._members(group_id))
            now = _now()
            self._db.executemany(
                "INSERT OR IGNORE INTO person_groups (person_id, group_id, added_at) VALUES (?,?,?)",
                [(pid, group_id, now) for pid in ids])
            self._db.commit()
            added = len(self._members(group_id)) - before
        self._remirror(ids)
        return added

    def _remirror(self, person_ids) -> None:
        for pid in person_ids:
            try:
                self._mirror(self.get(pid))
            except KeyError:
                continue

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
        names = {g["id"]: g["name"] for g in self.groups()}
        group_names = [names[g] for g in person.groups if g in names]
        tags = ["person", *(_tag(n) for n in group_names)]
        lines = [
            "---", "type: person", f"jarvis_person_id: {person.id}", f"updated_at: {person.updated_at}",
            "tags: [" + ", ".join(tags) + "]", "---", "",
            f"# {person.name}", "",
        ]
        if group_names:
            lines.append("- **Groups:** " + ", ".join(group_names))
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


def _tag(name: str) -> str:
    """Obsidian tag for a group name: lowercase, spaces to dashes, tag-safe characters only."""
    return re.sub(r"[^a-z0-9_/-]", "", name.lower().replace(" ", "-")) or "group"


def _clean_facts(facts) -> list[str]:
    if not facts:
        return []
    if isinstance(facts, str):
        facts = facts.splitlines()
    return [str(f).strip() for f in facts if str(f).strip()][:100]
