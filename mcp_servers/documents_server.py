"""Read-only "Documents" MCP server for JARVIS (stdio).

Exposes one folder (default: the user's Documents) to the brain as three tools:
``list_directory``, ``read_text_file`` and ``search_files``. It can never write,
delete or leave that folder: every path is resolved and checked against the root
(no ``..``, no absolute paths elsewhere, no symlink escapes).

Run:  python -m mcp_servers.documents_server "C:\\Users\\you\\Documents"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

MAX_READ_BYTES = 200_000
MAX_LIST = 200
MAX_SEARCH_RESULTS = 50
TEXT_SUFFIXES = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".log", ".ini", ".xml", ".html", ".py", ".js", ".ts",
    ".sql", ".ps1", ".bat", ".rtf",
}


def _root() -> Path:
    raw = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DOCS_ROOT") or str(Path.home() / "Documents")
    return Path(raw).expanduser().resolve()


ROOT = _root()
server = MCPServer("documents", instructions=f"Read-only access to files under {ROOT}.")


class OutsideRoot(ValueError):
    """A path that resolves outside the shared folder."""


def jailed(tool):
    """Turn an escape attempt into a plain answer instead of a tool error."""
    import functools  # noqa: PLC0415

    @functools.wraps(tool)
    def wrapper(*args, **kwargs):
        try:
            return tool(*args, **kwargs)
        except OutsideRoot as exc:
            return str(exc)

    return wrapper


def safe_path(relative: str) -> Path:
    """Resolve ``relative`` inside ROOT or raise OutsideRoot."""
    candidate = (ROOT / (relative or ".").strip().lstrip("\\/")).resolve()
    if candidate != ROOT and ROOT not in candidate.parents:
        raise OutsideRoot("That path is outside the shared Documents folder.")
    return candidate


@server.tool()
@jailed
def list_directory(path: str = "") -> str:
    """List files and folders in a folder of the user's Documents ('' = top level)."""
    folder = safe_path(path)
    if not folder.is_dir():
        return f"Not a folder: {path or '/'}"
    entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    lines = [f"{'[dir] ' if p.is_dir() else ''}{p.relative_to(ROOT)}" for p in entries[:MAX_LIST]]
    if len(entries) > MAX_LIST:
        lines.append(f"... and {len(entries) - MAX_LIST} more")
    return "\n".join(lines) or "(empty folder)"


@server.tool()
@jailed
def read_text_file(path: str) -> str:
    """Read a text file (txt, md, csv, json, ...) from the user's Documents. Large files are truncated."""
    file = safe_path(path)
    if not file.is_file():
        return f"No such file: {path}"
    if file.suffix.lower() not in TEXT_SUFFIXES:
        return f"{file.name} is not a plain-text file ({file.suffix or 'no extension'}); I can only read text files."
    data = file.read_bytes()[:MAX_READ_BYTES]
    text = data.decode("utf-8", errors="replace")
    suffix = "\n[truncated]" if file.stat().st_size > MAX_READ_BYTES else ""
    return text + suffix


@server.tool()
@jailed
def search_files(query: str, path: str = "") -> str:
    """Find files whose name contains ``query`` (case-insensitive) under a Documents folder."""
    wanted = query.strip().lower()
    if not wanted:
        return "Give me part of a file name to look for."
    base = safe_path(path)
    hits = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if wanted in name.lower():
                hits.append(str((Path(dirpath) / name).relative_to(ROOT)))
                if len(hits) >= MAX_SEARCH_RESULTS:
                    return "\n".join(hits) + "\n... (more results not shown)"
    return "\n".join(hits) or f"No files matching '{query}'."


if __name__ == "__main__":
    server.run()
