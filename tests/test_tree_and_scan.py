import os
import tempfile
import unittest

from sync_planning import (
    FILES_KEY,
    device_entries_to_tree,
    device_folder_paths,
    device_pdf_relpaths,
    list_local_pdf_relpaths,
    paths_to_tree,
)


class ListLocalPdfTests(unittest.TestCase):
    def test_lists_recursive_pdfs_with_posix_relpaths(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "Note"))
            open(os.path.join(root, "a.pdf"), "wb").close()
            open(os.path.join(root, "Note", "b.pdf"), "wb").close()
            open(os.path.join(root, "skip.txt"), "w").close()
            open(os.path.join(root, ".hidden.pdf"), "wb").close()
            self.assertEqual(
                list_local_pdf_relpaths(root),
                {"a.pdf", "Note/b.pdf"},
            )


class PathsToTreeTests(unittest.TestCase):
    def test_builds_nested_folder_tree(self):
        tree = paths_to_tree(
            [
                "Document",
                "Document/Note",
                "Document/Note/Sub",
                "Document/book",
            ]
        )
        self.assertIn("Document", tree)
        self.assertIn("Note", tree["Document"])
        self.assertIn("Sub", tree["Document"]["Note"])
        self.assertIn("book", tree["Document"])


class DeviceEntryHelpersTests(unittest.TestCase):
    def test_device_folder_paths_filters_and_includes_root(self):
        entries = [
            {"entry_type": "folder", "entry_path": "Document"},
            {"entry_type": "folder", "entry_path": "Document/Note"},
            {"entry_type": "document", "entry_path": "Document/Note/a.pdf"},
            {"entry_type": "folder", "entry_path": "Other"},
        ]
        self.assertEqual(
            device_folder_paths(entries),
            ["Document", "Document/Note"],
        )

    def test_device_pdf_relpaths(self):
        entries = [
            {"entry_type": "document", "entry_path": "Document/Note/a.pdf"},
            {"entry_type": "document", "entry_path": "Document/Note/sub/b.pdf"},
            {"entry_type": "document", "entry_path": "Document/other.pdf"},
        ]
        self.assertEqual(
            device_pdf_relpaths(entries, "Document/Note"),
            {"a.pdf", "sub/b.pdf"},
        )

    def test_device_entries_to_tree_includes_pdfs(self):
        entries = [
            {"entry_type": "folder", "entry_path": "Document"},
            {"entry_type": "folder", "entry_path": "Document/Note"},
            {"entry_type": "document", "entry_path": "Document/Note/a.pdf"},
            {"entry_type": "document", "entry_path": "Document/root.pdf"},
            {"entry_type": "document", "entry_path": "Document/Note/skip.txt"},
        ]
        tree = device_entries_to_tree(entries)
        self.assertEqual(tree["Document"][FILES_KEY], ["root.pdf"])
        self.assertEqual(tree["Document"]["Note"][FILES_KEY], ["a.pdf"])


if __name__ == "__main__":
    unittest.main()
