"""Plan and describe manual deletes on the Digital Paper Device tree."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class DeleteOp:
    kind: str  # "document" | "folder"
    path: str


def normalize_device_path(path: str) -> str:
    return (path or "").strip().rstrip("/")


def is_protected_device_root(path: str) -> bool:
    return normalize_device_path(path) == "Document"


def document_remote_path(parent_folder: str, filename: str) -> str:
    parent = normalize_device_path(parent_folder)
    name = (filename or "").strip()
    if not parent:
        return name
    return f"{parent}/{name}"


def plan_device_delete(
    entries: Iterable[dict], *, kind: str, path: str
) -> List[DeleteOp]:
    """Return delete operations in safe order (documents, then deepest folders)."""
    path = normalize_device_path(path)
    if not path:
        raise ValueError("Delete path cannot be empty.")
    if is_protected_device_root(path):
        raise ValueError("Cannot delete the device root Document/.")

    if kind == "document":
        return [DeleteOp(kind="document", path=path)]

    if kind != "folder":
        raise ValueError(f"Unsupported delete kind: {kind}")

    prefix = path + "/"
    docs: List[str] = []
    folders: List[str] = []
    for entry in entries:
        entry_path = normalize_device_path(entry.get("entry_path", ""))
        if not entry_path:
            continue
        etype = entry.get("entry_type")
        if etype == "document" and entry_path.startswith(prefix):
            docs.append(entry_path)
        elif etype == "folder" and (
            entry_path == path or entry_path.startswith(prefix)
        ):
            folders.append(entry_path)

    if path not in folders:
        folders.append(path)

    docs = sorted(set(docs))
    # Deepest folders first so parents are removed after children.
    folders = sorted(set(folders), key=lambda p: (-p.count("/"), -len(p), p))

    ops = [DeleteOp(kind="document", path=p) for p in docs]
    ops.extend(DeleteOp(kind="folder", path=p) for p in folders)
    return ops


def should_reset_device_folder_selection(
    selected_folder: str, *, deleted_path: str, deleted_kind: str
) -> bool:
    if deleted_kind != "folder":
        return False
    selected = normalize_device_path(selected_folder)
    deleted = normalize_device_path(deleted_path)
    if not selected or not deleted:
        return False
    return selected == deleted or selected.startswith(deleted + "/")


def format_device_delete_confirm(
    *, kind: str, path: str, ops: Sequence[DeleteOp]
) -> str:
    path = normalize_device_path(path)
    if kind == "document":
        return (
            f"Delete Document on device?\n\n"
            f"{path}\n\n"
            f"This cannot be undone from the app."
        )

    doc_ops = [op for op in ops if op.kind == "document"]
    folder_ops = [op for op in ops if op.kind == "folder"]
    non_pdf = [
        op.path
        for op in doc_ops
        if not op.path.lower().endswith(".pdf")
    ]
    lines = [
        f"Delete Device Folder on device?\n",
        f"{path}",
        f"\nThis will remove {len(doc_ops)} item(s) and {len(folder_ops)} folder(s), "
        f"including nested contents.",
        "",
        "Warning: non-PDF items under this folder are also removed on the device, "
        "even if they are not shown in the Device tree.",
    ]
    if non_pdf:
        lines.append("\nNon-PDF item(s) included:")
        lines.extend(f"  - {p}" for p in non_pdf[:20])
        if len(non_pdf) > 20:
            lines.append(f"  … and {len(non_pdf) - 20} more")
    lines.append("\nThis cannot be undone from the app.")
    return "\n".join(lines)


def apply_device_delete_ops(dp, ops: Sequence[DeleteOp]) -> None:
    """Execute planned deletes; raise on the first failure."""
    for op in ops:
        if op.kind == "document":
            dp.delete_document(op.path)
        elif op.kind == "folder":
            dp.delete_folder(op.path)
        else:
            raise ValueError(f"Unsupported delete kind: {op.kind}")
