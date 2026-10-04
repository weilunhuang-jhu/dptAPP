"""Helpers for filling Qt tree models from nested folder/file dicts."""

from __future__ import annotations

from typing import Dict, List

from PyQt5.QtGui import QStandardItem, QStandardItemModel

from sync_planning import FILES_KEY

PATH_ROLE = 256
NODE_KIND_ROLE = 257  # "folder" | "document" | "collection"


def fill_folder_tree_model(
    model: QStandardItemModel,
    tree: Dict[str, dict],
    path_role: int = PATH_ROLE,
    header: str = "Name",
) -> None:
    """Populate model from device_entries_to_tree / paths_to_tree output.

    Folder nodes store their full path; PDF Documents store the parent folder
    path in path_role and kind "document" in NODE_KIND_ROLE.
    """
    model.clear()
    model.setHorizontalHeaderLabels([header])

    def add_nodes(parent_item: QStandardItem, node: Dict[str, dict], prefix: str) -> None:
        files: List[str] = list(node.get(FILES_KEY, []))
        dir_names = sorted(k for k in node.keys() if k != FILES_KEY and isinstance(node[k], dict))

        for name in dir_names:
            path = f"{prefix}/{name}" if prefix else name
            item = QStandardItem(name)
            item.setEditable(False)
            item.setData(path, path_role)
            item.setData("folder", NODE_KIND_ROLE)
            parent_item.appendRow(item)
            add_nodes(item, node[name], path)

        for name in files:
            parent_path = prefix
            item = QStandardItem(name)
            item.setEditable(False)
            item.setData(parent_path, path_role)
            item.setData("document", NODE_KIND_ROLE)
            parent_item.appendRow(item)

    root = model.invisibleRootItem()
    add_nodes(root, tree, "")
