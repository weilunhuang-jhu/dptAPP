"""Pure planning helpers for Mirror Sync and Nested Sync Conflict detection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set


# Ignore tiny mtime skew between local FS and device clocks.
MTIME_TOLERANCE = timedelta(seconds=2)


@dataclass(frozen=True)
class MirrorPlan:
    to_copy: List[str]
    to_delete: List[str]
    target_newer: List[str]
    unchanged: List[str]


def list_local_pdf_relpaths(local_folder: str) -> Set[str]:
    """Return POSIX-relative paths of Documents under local_folder."""
    return set(list_local_pdf_mtimes(local_folder))


def list_local_pdf_mtimes(local_folder: str) -> Dict[str, datetime]:
    """Return POSIX-relative path -> UTC mtime for Documents under local_folder."""
    local_folder = os.path.abspath(local_folder)
    found: Dict[str, datetime] = {}
    for dirpath, _dirnames, filenames in os.walk(local_folder):
        for name in filenames:
            if name.startswith("."):
                continue
            if not name.lower().endswith(".pdf"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, local_folder).replace(os.sep, "/")
            found[rel] = datetime.fromtimestamp(os.path.getmtime(full), tz=timezone.utc)
    return found


FILES_KEY = "__files__"


def paths_to_tree(paths: Iterable[str]) -> Dict[str, dict]:
    """Build a nested dict tree from slash-separated folder paths."""
    root: Dict[str, dict] = {}
    for path in paths:
        parts = [p for p in path.strip("/").split("/") if p]
        node = root
        for part in parts:
            node = node.setdefault(part, {})
    return root


def _ensure_dir_node(root: Dict[str, dict], parts: Sequence[str]) -> Dict[str, dict]:
    node = root
    for part in parts:
        if part == FILES_KEY:
            continue
        child = node.setdefault(part, {})
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    return node


def device_entries_to_tree(
    entries: Iterable[dict], root_prefix: str = "Document"
) -> Dict[str, dict]:
    """Build a nested folder/file tree from device list/traverse entries.

    Folder nodes are dicts. PDF Documents are listed under the special key
    FILES_KEY as a sorted list of filenames.
    """
    root_prefix = root_prefix.rstrip("/")
    root: Dict[str, dict] = {}
    _ensure_dir_node(root, root_prefix.split("/"))

    for entry in entries:
        path = entry.get("entry_path", "").rstrip("/")
        if not path or not (path == root_prefix or path.startswith(root_prefix + "/")):
            continue
        parts = [p for p in path.split("/") if p]
        etype = entry.get("entry_type")
        if etype == "folder":
            _ensure_dir_node(root, parts)
        elif etype == "document":
            name = parts[-1] if parts else ""
            if not name.lower().endswith(".pdf") or name.startswith("."):
                continue
            parent = _ensure_dir_node(root, parts[:-1])
            files = parent.setdefault(FILES_KEY, [])
            if name not in files:
                files.append(name)

    def sort_files(node: Dict[str, dict]) -> None:
        if FILES_KEY in node:
            node[FILES_KEY] = sorted(node[FILES_KEY])
        for key, child in node.items():
            if key != FILES_KEY and isinstance(child, dict):
                sort_files(child)

    sort_files(root)
    return root


def device_folder_paths(entries: Iterable[dict], root_prefix: str = "Document") -> List[str]:
    """Folder entry_paths under root_prefix, including root_prefix itself when present."""
    root_prefix = root_prefix.rstrip("/")
    folders: Set[str] = set()
    for entry in entries:
        if entry.get("entry_type") != "folder":
            continue
        path = entry.get("entry_path", "").rstrip("/")
        if path == root_prefix or path.startswith(root_prefix + "/"):
            folders.add(path)
    if root_prefix not in folders:
        folders.add(root_prefix)
    return sorted(folders)


def device_pdf_relpaths(entries: Iterable[dict], device_folder: str) -> Set[str]:
    """PDF paths under device_folder, relative to device_folder."""
    return set(device_pdf_mtimes(entries, device_folder))


def parse_device_mtime(value: str) -> Optional[datetime]:
    """Parse device modified_date strings into UTC datetimes."""
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def device_pdf_mtimes(entries: Iterable[dict], device_folder: str) -> Dict[str, datetime]:
    """PDF relative paths under device_folder -> UTC mtime from entry modified_date."""
    device_folder = device_folder.rstrip("/")
    found: Dict[str, datetime] = {}
    prefix = device_folder + "/"
    for entry in entries:
        if entry.get("entry_type") != "document":
            continue
        path = entry.get("entry_path", "")
        name = os.path.basename(path)
        if not name.lower().endswith(".pdf") or name.startswith("."):
            continue
        if path == device_folder or not path.startswith(prefix):
            continue
        rel = path[len(prefix) :]
        mtime = parse_device_mtime(entry.get("modified_date", ""))
        if mtime is None:
            # Unknown mtime: treat as very old so a source file will be copied.
            mtime = datetime(1970, 1, 1, tzinfo=timezone.utc)
        found[rel] = mtime
    return found


def join_device_path(device_folder: str, relpath: str) -> str:
    device_folder = device_folder.rstrip("/")
    relpath = relpath.replace(os.sep, "/").lstrip("/")
    return f"{device_folder}/{relpath}" if relpath else device_folder


def plan_mirror(
    source_mtimes: Mapping[str, datetime],
    target_mtimes: Mapping[str, datetime],
) -> MirrorPlan:
    """Plan a Mirror Sync using mtimes.

    - Copy when missing on target, or source mtime is newer than target.
    - Skip when mtimes are equal within tolerance.
    - Record target_newer findings when target mtime is newer (do not overwrite).
    - Delete Documents that exist only on the target.
    """
    source_keys = set(source_mtimes)
    target_keys = set(target_mtimes)

    to_copy: List[str] = []
    target_newer: List[str] = []
    unchanged: List[str] = []

    for rel in sorted(source_keys):
        src_mtime = source_mtimes[rel]
        if rel not in target_mtimes:
            to_copy.append(rel)
            continue
        tgt_mtime = target_mtimes[rel]
        if src_mtime > tgt_mtime + MTIME_TOLERANCE:
            to_copy.append(rel)
        elif tgt_mtime > src_mtime + MTIME_TOLERANCE:
            target_newer.append(rel)
        else:
            unchanged.append(rel)

    return MirrorPlan(
        to_copy=to_copy,
        to_delete=sorted(target_keys - source_keys),
        target_newer=target_newer,
        unchanged=unchanged,
    )


def find_nested_checkpoint_conflicts(local_folder: str) -> List[str]:
    """Return Checkpoint paths that nest with local_folder (ancestors or descendants).

    The Checkpoint inside local_folder itself is ignored.
    """
    local_folder = os.path.abspath(local_folder)
    conflicts: List[str] = []

    # Ancestors (not including local_folder)
    parent = os.path.dirname(local_folder)
    while True:
        checkpoint = os.path.join(parent, ".sync")
        if os.path.isfile(checkpoint):
            conflicts.append(checkpoint)
        next_parent = os.path.dirname(parent)
        if next_parent == parent:
            break
        parent = next_parent

    # Descendants
    for dirpath, dirnames, filenames in os.walk(local_folder):
        if dirpath == local_folder:
            continue
        if ".sync" in filenames:
            conflicts.append(os.path.join(dirpath, ".sync"))

    return sorted(conflicts)


def explain_nested_conflicts(conflicts: Sequence[str], local_folder: str) -> str:
    """Human-readable explanation of Nested Sync Conflicts for a GUI dialog."""
    if not conflicts:
        return ""
    lines = [
        "Nested Sync Conflict: another Checkpoint overlaps this Local Folder.",
        f"Selected Local Folder: {local_folder}",
        "",
        "Overlapping Checkpoints:",
    ]
    for path in conflicts:
        lines.append(f"  - {path}")
    lines.extend(
        [
            "",
            "Bidirectional Sync at a parent and a child can fight: one Sync Pair's",
            "history does not know about the other's uploads, downloads, or deletes.",
            "Continue only if you understand that risk.",
        ]
    )
    return "\n".join(lines)
