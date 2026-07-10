from __future__ import annotations

import json
import re
import select
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from english_news_agent.obsidian_adapter import (
    ObsidianVaultAdapter,
    VaultListError,
    VaultNoteRef,
    VaultReadError,
    VaultTimeoutError,
    VaultWriteError,
)


@dataclass(frozen=True)
class StdioMcpConfig:
    command: str
    args: list[str] = field(default_factory=list)
    vault: str = ""
    timeout_seconds: float = 10


class StdioMcpClient:
    """Small JSON-RPC stdio client for MCP servers."""

    def __init__(self, command: str, args: list[str], timeout_seconds: float = 10):
        self.timeout_seconds = timeout_seconds
        self._next_id = 1
        self._lock = threading.Lock()
        self._process = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def initialize(self) -> None:
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "english-news-agent", "version": "0.1.0"},
            },
        )
        self.notify("notifications/initialized", {})

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
            while True:
                response = self._read_message()
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    raise RuntimeError(str(response["error"]))
                return response.get("result")

    def _send(self, message: dict[str, Any]) -> None:
        if self._process.stdin is None:
            raise RuntimeError("MCP process stdin is closed.")
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        framed = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload
        self._process.stdin.write(framed)
        self._process.stdin.flush()

    def _read_message(self) -> dict[str, Any]:
        if self._process.stdout is None:
            raise RuntimeError("MCP process stdout is closed.")
        header = b""
        while b"\r\n\r\n" not in header:
            chunk = self._read_exact(1)
            if not chunk:
                stderr = self._process.stderr.read().decode("utf-8", errors="replace") if self._process.stderr else ""
                raise RuntimeError(f"MCP process closed stdout. {stderr}".strip())
            header += chunk
        header_text = header.decode("ascii", errors="replace")
        match = re.search(r"Content-Length:\s*(\d+)", header_text, re.IGNORECASE)
        if not match:
            raise RuntimeError(f"MCP response missing Content-Length: {header_text!r}")
        length = int(match.group(1))
        body = self._read_exact(length)
        if len(body) != length:
            raise RuntimeError("MCP response body was truncated.")
        return json.loads(body.decode("utf-8"))

    def _read_exact(self, length: int) -> bytes:
        if self._process.stdout is None:
            raise RuntimeError("MCP process stdout is closed.")
        chunks: list[bytes] = []
        remaining = length
        while remaining > 0:
            ready, _write, _error = select.select([self._process.stdout], [], [], self.timeout_seconds)
            if not ready:
                raise TimeoutError("Timed out waiting for MCP stdio response.")
            chunk = self._process.stdout.read(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


class StdioMcpObsidianAdapter:
    """ObsidianVaultAdapter backed by obsidian-mcp-kr over stdio."""

    def __init__(self, config: StdioMcpConfig, client: StdioMcpClient | None = None):
        self.config = config
        self.client = client or StdioMcpClient(config.command, config.args, config.timeout_seconds)
        self.vault = config.vault
        if client is None:
            self.client.initialize()
        if not self.vault:
            self.vault = self._discover_first_vault()

    def close(self) -> None:
        self.client.close()

    def ensure_folder(self, folder_path: str) -> None:
        try:
            self._call_tool("create-directory", {"vault": self.vault, "path": _normalize(folder_path), "recursive": True})
        except RuntimeError as exc:
            message = str(exc)
            if "already exists" in message.lower():
                return
            raise VaultWriteError(f"MCP create-directory failed for {folder_path}: {exc}") from exc

    def read_note(self, note_path: str) -> str | None:
        filename, folder = _filename_and_folder(note_path)
        try:
            result = self._call_tool("read-note", _note_args(self.vault, filename, folder))
        except RuntimeError as exc:
            message = str(exc)
            if "not found" in message.lower() or "enoent" in message.lower():
                return None
            raise VaultReadError(f"MCP read-note failed for {note_path}: {exc}") from exc
        text = _tool_text(result)
        marker = "\n\n---\n"
        if marker in text:
            return text.split(marker, 1)[0]
        return text

    def write_note(self, note_path: str, content: str) -> None:
        filename, folder = _filename_and_folder(note_path)
        args = _note_args(self.vault, filename, folder) | {"content": content}
        try:
            self._call_tool("create-note", args)
        except RuntimeError as create_exc:
            message = str(create_exc).lower()
            if "exists" not in message and "already" not in message:
                raise VaultWriteError(f"MCP create-note failed for {note_path}: {create_exc}") from create_exc
            try:
                edit_args = _note_args(self.vault, filename, folder) | {"operation": "replace", "content": content}
                self._call_tool("edit-note", edit_args)
            except RuntimeError as edit_exc:
                raise VaultWriteError(f"MCP edit-note failed for {note_path}: {edit_exc}") from edit_exc

    def list_notes(self, folder_path: str, recursive: bool = True) -> list[VaultNoteRef]:
        try:
            result = self._call_tool(
                "search-vault",
                {
                    "vault": self.vault,
                    "query": ".md",
                    "path": _normalize(folder_path),
                    "searchType": "filename",
                    "caseSensitive": False,
                },
            )
        except RuntimeError as exc:
            raise VaultListError(f"MCP search-vault failed for {folder_path}: {exc}") from exc
        paths = _parse_search_paths(_tool_text(result))
        folder = _normalize(folder_path).rstrip("/")
        refs = []
        for path in paths:
            if not recursive:
                relative = PurePosixPath(path).relative_to(PurePosixPath(folder))
                if len(relative.parts) > 1:
                    continue
            refs.append(VaultNoteRef(path=path, modified=0))
        return refs

    def _discover_first_vault(self) -> str:
        result = self._call_tool("list-available-vaults", {})
        text = _tool_text(result)
        match = re.search(r"-\s+([^\n]+)", text)
        if not match:
            raise VaultReadError("MCP list-available-vaults did not return a vault name.")
        return match.group(1).strip()

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            return self.client.request("tools/call", {"name": name, "arguments": arguments})
        except TimeoutError as exc:
            raise VaultTimeoutError(f"MCP tool {name} timed out.") from exc


def _note_args(vault: str, filename: str, folder: str) -> dict[str, str]:
    args = {"vault": vault, "filename": filename}
    if folder:
        args["folder"] = folder
    return args


def _filename_and_folder(note_path: str) -> tuple[str, str]:
    path = PurePosixPath(_normalize(note_path))
    return path.name, "" if str(path.parent) == "." else path.parent.as_posix()


def _normalize(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute():
        raise ValueError(f"Vault paths must be relative: {path}")
    return pure.as_posix().strip("/")


def _tool_text(result: Any) -> str:
    content = result.get("content", []) if isinstance(result, dict) else []
    parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
    return "\n".join(parts).strip()


def _parse_search_paths(text: str) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        labeled = re.search(r"(?:file|path|filename match):\s*(.+?\.md)\b", line, re.IGNORECASE)
        if labeled:
            paths.append(_normalize(labeled.group(1).strip()))
            continue
        fallback = re.search(r"([^:]+?\.md)\b", line)
        if fallback and "/" in fallback.group(1):
            paths.append(_normalize(fallback.group(1).strip()))
    return sorted(set(paths))
