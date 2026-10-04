"""Execute Mirror Sync and Bidirectional Sync for Local↔Device and Zotero sources."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from typing import Callable, Dict, Set, Tuple

from sync_planning import (
    device_pdf_mtimes,
    explain_nested_conflicts,
    find_nested_checkpoint_conflicts,
    join_device_path,
    list_local_pdf_mtimes,
    plan_mirror,
)

StatusFn = Callable[[str], None]


def nested_conflict_message(local_folder: str) -> str:
    conflicts = find_nested_checkpoint_conflicts(local_folder)
    return explain_nested_conflicts(conflicts, local_folder)


def summarize_mirror_plan(plan) -> str:
    lines = [
        f"Mirror Sync will copy {len(plan.to_copy)} Document(s) "
        f"and delete {len(plan.to_delete)} Document(s) on the target.",
        f"Unchanged (skipped): {len(plan.unchanged)}",
        f"Target newer (skipped, listed as findings): {len(plan.target_newer)}",
    ]
    return "\n".join(lines)


def format_mirror_plan_details(plan, *, copy_label="Copy", delete_label="Delete") -> str:
    """Build confirm-dialog detail text including target-newer findings."""
    lines = [
        summarize_mirror_plan(plan),
        "",
        f"{copy_label} ({len(plan.to_copy)}):",
    ]
    lines.extend(f"  + {p}" for p in plan.to_copy[:30])
    if len(plan.to_copy) > 30:
        lines.append("  ...")

    lines.append(f"\n{delete_label} ({len(plan.to_delete)}):")
    lines.extend(f"  - {p}" for p in plan.to_delete[:30])
    if len(plan.to_delete) > 30:
        lines.append("  ...")

    if plan.target_newer:
        lines.append(
            f"\nFindings — target has a later mtime than source "
            f"({len(plan.target_newer)}; will NOT overwrite):"
        )
        lines.extend(f"  ! {p}" for p in plan.target_newer[:30])
        if len(plan.target_newer) > 30:
            lines.append("  ...")

    if plan.unchanged:
        lines.append(f"\nUnchanged skipped: {len(plan.unchanged)}")

    return "\n".join(lines)


def file_mtimes(path_by_rel: Dict[str, str]) -> Dict[str, datetime]:
    """Build relpath -> UTC mtime for existing local files."""
    out: Dict[str, datetime] = {}
    for rel, path in path_by_rel.items():
        if os.path.isfile(path):
            out[rel] = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    return out


def mirror_local_to_device(dp, local_folder: str, device_folder: str, status: StatusFn = print):
    local_folder = os.path.abspath(local_folder)
    device_folder = device_folder.rstrip("/")
    os.makedirs(local_folder, exist_ok=True)
    if not dp.path_exists(device_folder):
        dp.new_folder(device_folder)

    entries = dp.traverse_folder(device_folder)
    plan = plan_mirror(
        list_local_pdf_mtimes(local_folder),
        device_pdf_mtimes(entries, device_folder),
    )
    status(summarize_mirror_plan(plan))

    for rel in plan.to_copy:
        local_path = os.path.join(local_folder, rel.replace("/", os.sep))
        remote_path = join_device_path(device_folder, rel)
        status(f"Upload {rel}")
        dp.upload_file(local_path, remote_path)

    for rel in plan.to_delete:
        remote_path = join_device_path(device_folder, rel)
        status(f"Delete on device {rel}")
        dp.delete_document(remote_path)

    return plan


def mirror_device_to_local(dp, local_folder: str, device_folder: str, status: StatusFn = print):
    local_folder = os.path.abspath(local_folder)
    device_folder = device_folder.rstrip("/")
    os.makedirs(local_folder, exist_ok=True)

    entries = dp.traverse_folder(device_folder)
    plan = plan_mirror(
        device_pdf_mtimes(entries, device_folder),
        list_local_pdf_mtimes(local_folder),
    )
    status(summarize_mirror_plan(plan))

    for rel in plan.to_copy:
        local_path = os.path.join(local_folder, rel.replace("/", os.sep))
        remote_path = join_device_path(device_folder, rel)
        status(f"Download {rel}")
        dp.download_file(remote_path, local_path)

    for rel in plan.to_delete:
        local_path = os.path.join(local_folder, rel.replace("/", os.sep))
        status(f"Delete local {rel}")
        if os.path.isfile(local_path):
            os.remove(local_path)

    return plan


def bidirectional_local_device(dp, local_folder: str, device_folder: str, status: StatusFn = print) -> None:
    local_folder = os.path.abspath(local_folder)
    device_folder = device_folder.rstrip("/")
    os.makedirs(local_folder, exist_ok=True)
    dp.assume_yes = True
    status(f"Bidirectional Sync {local_folder} ↔ {device_folder}")
    dp.sync(local_folder, device_folder)


def collect_zotero_pdfs(
    zot,
    collection_key: str,
    storage_home: str,
) -> Set[Tuple[str, str]]:
    """Return set of (relpath, absolute_source_path) for PDFs in a collection tree."""
    results: Set[Tuple[str, str]] = set()

    def walk(key: str, prefix: str) -> None:
        for item in zot.collection_items(key):
            data = item.get("data", {})
            filename = data.get("filename")
            if not filename or not filename.lower().endswith(".pdf"):
                continue
            if filename.startswith("."):
                continue
            rel = f"{prefix}/{filename}" if prefix else filename
            src = os.path.join(storage_home, item["key"], filename)
            results.add((rel.replace("\\", "/"), src))

        try:
            subs = zot.collections_sub(key)
        except Exception:
            subs = []
        for sub in subs:
            name = sub["data"]["name"]
            child_prefix = f"{prefix}/{name}" if prefix else name
            walk(sub["key"], child_prefix)

    walk(collection_key, "")
    return results


def mirror_zotero_to_local(
    zot,
    collection_key: str,
    local_folder: str,
    storage_home: str,
    status: StatusFn = print,
):
    local_folder = os.path.abspath(local_folder)
    os.makedirs(local_folder, exist_ok=True)
    pairs = collect_zotero_pdfs(zot, collection_key, storage_home)
    src_by_rel = {rel: src for rel, src in pairs}
    plan = plan_mirror(file_mtimes(src_by_rel), list_local_pdf_mtimes(local_folder))
    status(summarize_mirror_plan(plan))

    for rel in plan.to_copy:
        dest = os.path.join(local_folder, rel.replace("/", os.sep))
        parent_dir = os.path.dirname(dest)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        src = src_by_rel[rel]
        status(f"Copy {rel}")
        shutil.copy2(src, dest)

    for rel in plan.to_delete:
        path = os.path.join(local_folder, rel.replace("/", os.sep))
        status(f"Delete local {rel}")
        if os.path.isfile(path):
            os.remove(path)

    return plan


def mirror_zotero_to_device(
    zot,
    dp,
    collection_key: str,
    device_folder: str,
    storage_home: str,
    status: StatusFn = print,
):
    device_folder = device_folder.rstrip("/")
    if not dp.path_exists(device_folder):
        dp.new_folder(device_folder)

    pairs = collect_zotero_pdfs(zot, collection_key, storage_home)
    src_by_rel = {rel: src for rel, src in pairs}
    entries = dp.traverse_folder(device_folder)
    plan = plan_mirror(
        file_mtimes(src_by_rel), device_pdf_mtimes(entries, device_folder)
    )
    status(summarize_mirror_plan(plan))

    for rel in plan.to_copy:
        remote_path = join_device_path(device_folder, rel)
        status(f"Upload {rel}")
        dp.upload_file(src_by_rel[rel], remote_path)

    for rel in plan.to_delete:
        remote_path = join_device_path(device_folder, rel)
        status(f"Delete on device {rel}")
        dp.delete_document(remote_path)

    return plan
