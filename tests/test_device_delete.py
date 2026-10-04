import unittest

from device_delete import (
    DeleteOp,
    format_device_delete_confirm,
    is_protected_device_root,
    plan_device_delete,
    should_reset_device_folder_selection,
)


class DeviceDeleteTests(unittest.TestCase):
    def test_protects_document_root(self):
        self.assertTrue(is_protected_device_root("Document"))
        self.assertTrue(is_protected_device_root("Document/"))
        self.assertFalse(is_protected_device_root("Document/Note"))

    def test_plans_single_document_delete(self):
        entries = [
            {"entry_type": "document", "entry_path": "Document/Note/a.pdf"},
        ]
        ops = plan_device_delete(
            entries, kind="document", path="Document/Note/a.pdf"
        )
        self.assertEqual(ops, [DeleteOp(kind="document", path="Document/Note/a.pdf")])

    def test_plans_recursive_folder_delete_docs_then_deepest_folders(self):
        entries = [
            {"entry_type": "folder", "entry_path": "Document/Note"},
            {"entry_type": "folder", "entry_path": "Document/Note/sub"},
            {"entry_type": "document", "entry_path": "Document/Note/a.pdf"},
            {"entry_type": "document", "entry_path": "Document/Note/sub/b.pdf"},
            {"entry_type": "document", "entry_path": "Document/Note/sub/notes.txt"},
            {"entry_type": "document", "entry_path": "Document/Other/c.pdf"},
        ]
        ops = plan_device_delete(entries, kind="folder", path="Document/Note")
        self.assertEqual(
            ops,
            [
                DeleteOp(kind="document", path="Document/Note/a.pdf"),
                DeleteOp(kind="document", path="Document/Note/sub/b.pdf"),
                DeleteOp(kind="document", path="Document/Note/sub/notes.txt"),
                DeleteOp(kind="folder", path="Document/Note/sub"),
                DeleteOp(kind="folder", path="Document/Note"),
            ],
        )

    def test_refuses_plan_for_protected_root(self):
        with self.assertRaises(ValueError):
            plan_device_delete([], kind="folder", path="Document")

    def test_resets_selection_when_deleted_folder_is_selected_or_ancestor(self):
        self.assertTrue(
            should_reset_device_folder_selection(
                "Document/Note", deleted_path="Document/Note", deleted_kind="folder"
            )
        )
        self.assertTrue(
            should_reset_device_folder_selection(
                "Document/Note/sub",
                deleted_path="Document/Note",
                deleted_kind="folder",
            )
        )
        self.assertFalse(
            should_reset_device_folder_selection(
                "Document/Other",
                deleted_path="Document/Note",
                deleted_kind="folder",
            )
        )
        self.assertFalse(
            should_reset_device_folder_selection(
                "Document/Note",
                deleted_path="Document/Note/a.pdf",
                deleted_kind="document",
            )
        )

    def test_confirm_text_warns_for_folder_non_pdfs(self):
        ops = [
            DeleteOp(kind="document", path="Document/Note/a.pdf"),
            DeleteOp(kind="document", path="Document/Note/notes.txt"),
            DeleteOp(kind="folder", path="Document/Note"),
        ]
        text = format_device_delete_confirm(kind="folder", path="Document/Note", ops=ops)
        self.assertIn("Document/Note", text)
        self.assertIn("non-PDF", text)
        self.assertIn("notes.txt", text)

    def test_confirm_text_for_document_is_simple(self):
        ops = [DeleteOp(kind="document", path="Document/Note/a.pdf")]
        text = format_device_delete_confirm(
            kind="document", path="Document/Note/a.pdf", ops=ops
        )
        self.assertIn("Document/Note/a.pdf", text)
        self.assertNotIn("non-PDF", text)


if __name__ == "__main__":
    unittest.main()
