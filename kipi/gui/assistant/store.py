"""One assistant conversation per project, kept under KiPI's data folder.

The key is the board's name, project directory and file, so reopening the same board
brings its conversation back, while another board gets a conversation of its own. The
model configuration stays global; only the chat follows the project.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from kipi.launcher.paths import data_dir


def project_key(snapshot: Any) -> str:
    """A stable id for the board a conversation belongs to."""
    if snapshot is None:
        return "no-board"
    parts = [getattr(snapshot, "board_name", ""), getattr(snapshot, "project_dir", ""),
             getattr(snapshot, "file", "")]
    ident = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(ident.encode("utf-8")).hexdigest()[:20]


class ConversationStore:
    """Reads and writes the conversation file of the project currently in use."""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root is not None else data_dir() / "assistant"
        self.key = ""
        self.path: Optional[Path] = None

    def use(self, key: str) -> None:
        self.key = key
        self.path = self.root / f"{key}.json"

    def load(self) -> Dict[str, Any]:
        if self.path is None or not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def save(self, data: Dict[str, Any]) -> None:
        if self.path is None:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            pass                    # a read-only disk must not break the chat

    def clear(self) -> None:
        if self.path is None:
            return
        try:
            self.path.unlink()
        except OSError:
            pass
