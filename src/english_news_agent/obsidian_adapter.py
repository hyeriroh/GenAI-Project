from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from time import time
from typing import Protocol




class VaultAdapterError(RuntimeError):
    """Base error for Obsidian vault adapter failures."""


class VaultTimeoutError(VaultAdapterError):
    """Raised when a vault operation times out."""


class VaultReadError(VaultAdapterError):
    """Raised when a note read operation fails unexpectedly."""


class VaultWriteError(VaultAdapterError):
    """Raised when a note or folder write operation fails."""


class VaultListError(VaultAdapterError):
    """Raised when listing vault notes fails."""


@dataclass(frozen=True)
class VaultNoteRef:
    path: str
    modified: float = 0


class ObsidianVaultAdapter(Protocol):
    """Minimal vault operations needed by the vocabulary test orchestrator."""

    def ensure_folder(self, folder_path: str) -> None:
        ...

    def read_note(self, note_path: str) -> str | None:
        ...

    def write_note(self, note_path: str, content: str) -> None:
        ...

    def list_notes(self, folder_path: str, recursive: bool = True) -> list[VaultNoteRef]:
        ...


class FileSystemObsidianAdapter:
    """Adapter for a local Obsidian vault path."""

    def __init__(self, vault_path: str | Path):
        self.vault_path = Path(vault_path).expanduser()

    def ensure_folder(self, folder_path: str) -> None:
        try:
            self._resolve(folder_path).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise VaultWriteError(f"Could not ensure folder {folder_path}: {exc}") from exc

    def read_note(self, note_path: str) -> str | None:
        path = self._resolve(note_path)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise VaultReadError(f"Could not read note {note_path}: {exc}") from exc

    def write_note(self, note_path: str, content: str) -> None:
        path = self._resolve(note_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise VaultWriteError(f"Could not write note {note_path}: {exc}") from exc

    def list_notes(self, folder_path: str, recursive: bool = True) -> list[VaultNoteRef]:
        folder = self._resolve(folder_path)
        if not folder.exists():
            return []
        try:
            iterator = folder.rglob("*.md") if recursive else folder.glob("*.md")
            refs = []
            for path in iterator:
                refs.append(
                    VaultNoteRef(
                        path=path.relative_to(self.vault_path).as_posix(),
                        modified=path.stat().st_mtime,
                    )
                )
            return refs
        except OSError as exc:
            raise VaultListError(f"Could not list notes under {folder_path}: {exc}") from exc

    def _resolve(self, vault_relative_path: str) -> Path:
        relative = PurePosixPath(vault_relative_path)
        if relative.is_absolute():
            raise ValueError(f"Vault paths must be relative: {vault_relative_path}")
        return self.vault_path / Path(*relative.parts)


class MockObsidianAdapter:
    """In-memory MCP-style adapter for orchestrator tests and demos."""

    def __init__(
        self,
        files: dict[str, str] | None = None,
        fail_on_read: set[str] | None = None,
        fail_on_write: set[str] | None = None,
        fail_on_list: set[str] | None = None,
        fail_on_ensure: set[str] | None = None,
    ):
        self.files: dict[str, str] = {}
        self.folders: set[str] = set()
        self.modified: dict[str, float] = {}
        self.fail_on_read = {_normalize_vault_path(path) for path in fail_on_read or set()}
        self.fail_on_write = {_normalize_vault_path(path) for path in fail_on_write or set()}
        self.fail_on_list = {_normalize_vault_path(path) for path in fail_on_list or set()}
        self.fail_on_ensure = {_normalize_vault_path(path) for path in fail_on_ensure or set()}
        for path, content in (files or {}).items():
            normalized = _normalize_vault_path(path)
            self.files[normalized] = content
            self.modified[normalized] = time()
            self._remember_parent_folders(normalized)

    def ensure_folder(self, folder_path: str) -> None:
        normalized = _normalize_vault_path(folder_path)
        if normalized in self.fail_on_ensure:
            raise VaultWriteError(f"Injected folder creation failure: {normalized}")
        self.folders.add(normalized)

    def read_note(self, note_path: str) -> str | None:
        normalized = _normalize_vault_path(note_path)
        if normalized in self.fail_on_read:
            raise VaultReadError(f"Injected read failure: {normalized}")
        return self.files.get(normalized)

    def write_note(self, note_path: str, content: str) -> None:
        normalized = _normalize_vault_path(note_path)
        if normalized in self.fail_on_write:
            raise VaultWriteError(f"Injected write failure: {normalized}")
        self.files[normalized] = content
        self.modified[normalized] = time()
        self._remember_parent_folders(normalized)

    def list_notes(self, folder_path: str, recursive: bool = True) -> list[VaultNoteRef]:
        folder = _normalize_vault_path(folder_path).rstrip("/")
        if folder in self.fail_on_list:
            raise VaultListError(f"Injected list failure: {folder}")
        prefix = f"{folder}/" if folder else ""
        refs: list[VaultNoteRef] = []
        for path in self.files:
            if not path.endswith(".md") or not path.startswith(prefix):
                continue
            relative = path[len(prefix) :]
            if not recursive and "/" in relative:
                continue
            refs.append(VaultNoteRef(path=path, modified=self.modified.get(path, 0)))
        return refs

    def _remember_parent_folders(self, note_path: str) -> None:
        parent = PurePosixPath(note_path).parent
        while str(parent) not in {".", ""}:
            self.folders.add(parent.as_posix())
            parent = parent.parent


def _normalize_vault_path(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute():
        raise ValueError(f"Vault paths must be relative: {path}")
    return pure.as_posix().strip("/")
