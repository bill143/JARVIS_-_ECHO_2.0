"""JARVIS toolbox config: MCP servers, tool on/off switches, skills, secrets.

Everything lives locally under ``%USERPROFILE%\\JARVIS\\toolbox`` (or
``JARVIS_DATA_DIR``):

* ``config.json``  - servers, disabled tools, skills (no secret values ever).
* ``secrets.json`` - ``{NAME: value}`` for API keys / tokens. Written only by
  ``set_secret``; the API returns names and "is set", never values, and nothing
  here is logged.
* ``skills/<name>/SKILL.md`` - imported skills (agentskills.io format).
  The ``skills`` folder is also a drop folder: skill folders, folders of skill
  folders and .zip files copied into it are picked up by ``scan_skill_folder``
  (at startup, when the Skills & Tools page opens, and by its Rescan button).
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

TRANSPORTS = ("stdio", "http", "sse")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _().-]{0,63}$")
_SECRET_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_SKILL_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_SKILL_FILE_BYTES = 512 * 1024
MAX_SKILL_ZIP_BYTES = 200 * 1024 * 1024
MAX_SCANNED_SKILLS = 2000
_SKIP_DIRS = {"__MACOSX", ".git", "node_modules", "__pycache__"}
REPO_ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_dir() -> Path:
    # Not %LOCALAPPDATA%: when JARVIS is started from a packaged (MSIX) app such as
    # the Claude desktop app, Windows silently redirects AppData writes into that
    # app's private folder, so the data was invisible in File Explorer and missing
    # when JARVIS was started from its own shortcut. The user profile is not redirected.
    base = os.getenv("JARVIS_DATA_DIR") or str(Path.home() / "JARVIS")
    return Path(base) / "toolbox"


def documents_dir() -> str:
    return os.getenv("JARVIS_DOCUMENTS_DIR") or str(Path.home() / "Documents")


# Free, no-key servers that ship ready to use, plus one-click entries that need a sign-in.
def presets() -> dict[str, dict]:
    py = sys.executable
    return {
        "documents": {
            "name": "Documents (read-only)", "transport": "stdio", "command": py,
            "args": ["-m", "mcp_servers.documents_server", documents_dir()], "cwd": str(REPO_ROOT),
            "about": f"List, search and read text files in {documents_dir()}. Read-only, never leaves that folder.",
            "default": True, "needs": [],
        },
        "fetch": {
            "name": "Web fetch", "transport": "stdio", "command": py, "args": ["-m", "mcp_server_fetch"],
            "about": "Fetch a web page and read it as text (official MCP fetch server). No key needed.",
            "default": True, "needs": [],
        },
        "gmail": {
            "name": "Gmail", "transport": "stdio", "command": "npx",
            "args": ["-y", "@gongrzhe/server-gmail-autoauth-mcp"],
            "about": "Read, search and draft Gmail. Needs a one-time Google sign-in on this PC.",
            "default": False,
            "needs": ["Google OAuth client file at %USERPROFILE%\\.gmail-mcp\\gcp-oauth.keys.json",
                      "One-time sign-in: npx @gongrzhe/server-gmail-autoauth-mcp auth"],
        },
        "google_calendar": {
            "name": "Google Calendar", "transport": "stdio", "command": "npx",
            "args": ["-y", "@cocal/google-calendar-mcp"], "secret_env": ["GOOGLE_OAUTH_CREDENTIALS"],
            "about": "Read and create Google Calendar events. Needs a one-time Google sign-in on this PC.",
            "default": False,
            "needs": ["Secret GOOGLE_OAUTH_CREDENTIALS = path to your Google OAuth client JSON",
                      "One-time sign-in: npx @cocal/google-calendar-mcp auth"],
        },
    }


class ToolboxStore:
    def __init__(self, directory: Path | None = None, seed_presets: bool = True) -> None:
        self.dir = Path(directory) if directory else default_dir()
        self.skills_dir = self.dir / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._config_path = self.dir / "config.json"
        self._secrets_path = self.dir / "secrets.json"
        self._lock = threading.RLock()
        self._config = self._load(self._config_path, {"servers": [], "disabled_builtin": [], "skills": []})
        if seed_presets and not self._config.get("seeded"):
            for preset_id, preset in presets().items():
                if preset["default"]:
                    self._add_server_unlocked(self._from_preset(preset_id, preset))
            self._config["seeded"] = True
            self._save()

    # ---- persistence ---------------------------------------------------
    @staticmethod
    def _load(path: Path, default: dict) -> dict:
        if not path.exists():
            return copy.deepcopy(default)
        return {**copy.deepcopy(default), **json.loads(path.read_text(encoding="utf-8"))}

    def _save(self) -> None:
        tmp = self._config_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._config, indent=2), encoding="utf-8")
        tmp.replace(self._config_path)

    # ---- servers --------------------------------------------------------
    def servers(self) -> list[dict]:
        with self._lock:
            return copy.deepcopy(self._config["servers"])

    def server(self, server_id: str) -> dict:
        for s in self.servers():
            if s["id"] == server_id:
                return s
        raise KeyError(server_id)

    @staticmethod
    def validate_server(cfg: dict) -> dict:
        name = str(cfg.get("name", "")).strip()
        if not _NAME_RE.match(name):
            raise ValueError("Name: 1-64 letters, numbers, spaces, dots, dashes or underscores.")
        transport = cfg.get("transport", "stdio")
        if transport not in TRANSPORTS:
            raise ValueError("Type must be stdio, http or sse.")
        clean = {"name": name, "transport": transport, "enabled": bool(cfg.get("enabled", True)),
                 "preset": str(cfg.get("preset", "")), "disabled_tools": list(cfg.get("disabled_tools", []))}
        if transport == "stdio":
            command = str(cfg.get("command", "")).strip()
            if not command:
                raise ValueError("A stdio server needs a command (e.g. npx, uvx, python).")
            clean.update(command=command, args=[str(a) for a in cfg.get("args", [])][:40],
                         cwd=str(cfg.get("cwd", "") or ""))
        else:
            url = str(cfg.get("url", "")).strip()
            if not re.match(r"^https?://", url):
                raise ValueError("An http/sse server needs a URL starting with http:// or https://.")
            clean.update(url=url)
        secret_env = [str(s) for s in cfg.get("secret_env", [])]
        auth_secret = str(cfg.get("auth_secret", "") or "")
        for s in [*secret_env, *([auth_secret] if auth_secret else [])]:
            if not _SECRET_RE.match(s):
                raise ValueError(f"Secret names are UPPER_CASE letters, digits and _ (got {s!r}).")
        clean.update(secret_env=secret_env, auth_secret=auth_secret)
        return clean

    def _add_server_unlocked(self, cfg: dict) -> dict:
        server = {"id": uuid.uuid4().hex[:12], **self.validate_server(cfg), "added_at": _now()}
        if any(s["name"].lower() == server["name"].lower() for s in self._config["servers"]):
            raise ValueError(f"A server named {server['name']!r} already exists.")
        self._config["servers"].append(server)
        return server

    def add_server(self, cfg: dict) -> dict:
        with self._lock:
            server = self._add_server_unlocked(cfg)
            self._save()
            return copy.deepcopy(server)

    @staticmethod
    def _from_preset(preset_id: str, preset: dict) -> dict:
        keep = ("name", "transport", "command", "args", "cwd", "url", "secret_env")
        return {**{k: preset[k] for k in keep if k in preset}, "preset": preset_id, "enabled": True}

    def add_preset(self, preset_id: str) -> dict:
        catalog = presets()
        if preset_id not in catalog:
            raise KeyError(preset_id)
        return self.add_server(self._from_preset(preset_id, catalog[preset_id]))

    def update_server(self, server_id: str, changes: dict) -> dict:
        with self._lock:
            for s in self._config["servers"]:
                if s["id"] == server_id:
                    if "enabled" in changes:
                        s["enabled"] = bool(changes["enabled"])
                    if "disabled_tools" in changes:
                        s["disabled_tools"] = sorted({str(t) for t in changes["disabled_tools"]})
                    self._save()
                    return copy.deepcopy(s)
        raise KeyError(server_id)

    def remove_server(self, server_id: str) -> None:
        with self._lock:
            before = len(self._config["servers"])
            self._config["servers"] = [s for s in self._config["servers"] if s["id"] != server_id]
            if len(self._config["servers"]) == before:
                raise KeyError(server_id)
            self._save()

    # ---- built-in tool switches ----------------------------------------
    def disabled_builtin(self) -> set[str]:
        with self._lock:
            return set(self._config["disabled_builtin"])

    def set_builtin_enabled(self, tool: str, enabled: bool) -> None:
        with self._lock:
            disabled = set(self._config["disabled_builtin"])
            (disabled.discard if enabled else disabled.add)(tool)
            self._config["disabled_builtin"] = sorted(disabled)
            self._save()

    # ---- secrets (values never leave this class except into a server's env) ----
    def _secrets(self) -> dict[str, str]:
        return self._load(self._secrets_path, {})

    def secret_names(self) -> list[str]:
        return sorted(self._secrets())

    def set_secret(self, name: str, value: str) -> None:
        if not _SECRET_RE.match(name or ""):
            raise ValueError("Secret names are UPPER_CASE letters, digits and _ (e.g. GITHUB_TOKEN).")
        if not value or len(value) > 8000:
            raise ValueError("Secret value must be 1-8000 characters.")
        with self._lock:
            secrets = self._secrets()
            secrets[name] = value
            self._secrets_path.write_text(json.dumps(secrets), encoding="utf-8")

    def delete_secret(self, name: str) -> None:
        with self._lock:
            secrets = self._secrets()
            if name not in secrets:
                raise KeyError(name)
            del secrets[name]
            self._secrets_path.write_text(json.dumps(secrets), encoding="utf-8")

    def resolve_secrets(self, names: list[str]) -> tuple[dict[str, str], list[str]]:
        """``({name: value}, [missing names])`` for launching a server."""
        secrets = self._secrets()
        found = {n: secrets[n] for n in names if n in secrets}
        return found, [n for n in names if n not in secrets]

    # ---- skills (SKILL.md) ---------------------------------------------
    def skills(self) -> list[dict]:
        with self._lock:
            return copy.deepcopy(self._config["skills"])

    def import_skill(self, skill_md: str, source: str = "upload") -> dict:
        meta, _body = parse_skill_md(skill_md)
        name = meta["name"]
        with self._lock:
            folder = self.skills_dir / name
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "SKILL.md").write_text(skill_md, encoding="utf-8")
            entry = {"name": name, "description": meta["description"], "enabled": True, "source": source,
                     "added_at": _now()}
            self._config["skills"] = [s for s in self._config["skills"] if s["name"] != name] + [entry]
            self._save()
            return dict(entry)

    def scan_skill_folder(self) -> dict:
        """Register every new SKILL.md found under the skills folder (nested folders and .zip files).

        Skills already registered (by name) are left alone, so a rescan is safe to
        repeat. Returns ``{"imported": [names], "skipped": n, "problems": [text]}``.
        """
        known = {s["name"] for s in self.skills()}
        imported: list[str] = []
        problems: list[str] = []
        skipped = 0
        for source, text in self._skill_texts_in_folder(problems):
            try:
                meta, _ = parse_skill_md(text)
            except ValueError as exc:
                problems.append(f"{source}: {exc}")
                continue
            if meta["name"] in known:
                skipped += 1
                continue
            try:
                self.import_skill(text, source=f"folder:{source}")
            except (ValueError, OSError) as exc:
                problems.append(f"{source}: {exc}")
                continue
            known.add(meta["name"])
            imported.append(meta["name"])
        return {"imported": imported, "skipped": skipped, "problems": problems[:50]}

    def _skill_texts_in_folder(self, problems: list[str]):
        """Yield ``(source, SKILL.md text)`` for loose SKILL.md files and SKILL.md inside zips."""
        root = self.skills_dir
        count = 0
        for current, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith("."))
            for filename in sorted(files):
                if count >= MAX_SCANNED_SKILLS:
                    problems.append(f"Stopped after {MAX_SCANNED_SKILLS} skills.")
                    return
                path = Path(current) / filename
                rel = path.relative_to(root).as_posix()
                try:
                    if filename == "SKILL.md":
                        if path.stat().st_size > MAX_SKILL_FILE_BYTES:
                            problems.append(f"{rel}: larger than 512 KB")
                            continue
                        count += 1
                        yield rel, path.read_text(encoding="utf-8", errors="replace")
                    elif filename.lower().endswith(".zip"):
                        if path.stat().st_size > MAX_SKILL_ZIP_BYTES:
                            problems.append(f"{rel}: zip larger than 200 MB")
                            continue
                        with zipfile.ZipFile(path) as archive:
                            for info in archive.infolist():
                                inner = info.filename.replace("\\", "/")
                                if inner.split("/")[-1] != "SKILL.md" or "__MACOSX" in inner:
                                    continue
                                if info.file_size > MAX_SKILL_FILE_BYTES:
                                    problems.append(f"{rel}:{inner}: larger than 512 KB")
                                    continue
                                count += 1
                                # Read in memory only: nothing from the zip is written
                                # to disk except the validated SKILL.md (import_skill).
                                yield f"{rel}:{inner}", archive.read(info).decode("utf-8", "replace")
                except (OSError, zipfile.BadZipFile) as exc:
                    problems.append(f"{rel}: {exc}")

    def skill_body(self, name: str) -> str:
        if not any(s["name"] == name for s in self.skills()):
            raise KeyError(name)
        return parse_skill_md((self.skills_dir / name / "SKILL.md").read_text(encoding="utf-8"))[1]

    def set_skill_enabled(self, name: str, enabled: bool) -> dict:
        with self._lock:
            for s in self._config["skills"]:
                if s["name"] == name:
                    s["enabled"] = bool(enabled)
                    self._save()
                    return dict(s)
        raise KeyError(name)

    def remove_skill(self, name: str) -> None:
        with self._lock:
            before = len(self._config["skills"])
            self._config["skills"] = [s for s in self._config["skills"] if s["name"] != name]
            if len(self._config["skills"]) == before:
                raise KeyError(name)
            skill_file = self.skills_dir / name / "SKILL.md"
            if skill_file.exists():
                skill_file.unlink()
            self._save()


def parse_skill_md(text: str) -> tuple[dict, str]:
    """Validate an agentskills.io SKILL.md: YAML frontmatter with name + description, then instructions."""
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter (---).")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter is not closed with ---.")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"SKILL.md frontmatter is not valid YAML: {exc}") from exc
    name = str(meta.get("name", "")).strip()
    description = str(meta.get("description", "")).strip()
    if not _SKILL_RE.match(name):
        raise ValueError("SKILL.md needs a 'name' of lowercase letters, digits and dashes.")
    if not description:
        raise ValueError("SKILL.md needs a 'description'.")
    body = parts[2].strip()
    if not body:
        raise ValueError("SKILL.md has no instructions after the frontmatter.")
    return {"name": name, "description": description[:500]}, body
