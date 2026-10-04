import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sync_planning import MirrorPlan, find_nested_checkpoint_conflicts, plan_mirror


def _ts(hours=0):
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(hours=hours)


class PlanMirrorTests(unittest.TestCase):
    def test_copies_missing_and_deletes_extras(self):
        plan = plan_mirror(
            source_mtimes={"a.pdf": _ts(1), "sub/b.pdf": _ts(1)},
            target_mtimes={"sub/b.pdf": _ts(1), "old.pdf": _ts(0)},
        )
        self.assertEqual(plan.to_copy, ["a.pdf"])
        self.assertEqual(plan.to_delete, ["old.pdf"])
        self.assertEqual(plan.unchanged, ["sub/b.pdf"])
        self.assertEqual(plan.target_newer, [])

    def test_copies_when_source_newer(self):
        plan = plan_mirror(
            source_mtimes={"a.pdf": _ts(5)},
            target_mtimes={"a.pdf": _ts(1)},
        )
        self.assertEqual(plan.to_copy, ["a.pdf"])
        self.assertEqual(plan.target_newer, [])
        self.assertEqual(plan.unchanged, [])

    def test_skips_unchanged_same_mtime(self):
        plan = plan_mirror(
            source_mtimes={"a.pdf": _ts(1)},
            target_mtimes={"a.pdf": _ts(1)},
        )
        self.assertEqual(plan.to_copy, [])
        self.assertEqual(plan.unchanged, ["a.pdf"])
        self.assertEqual(plan.to_delete, [])

    def test_lists_target_newer_without_copying(self):
        plan = plan_mirror(
            source_mtimes={"a.pdf": _ts(1)},
            target_mtimes={"a.pdf": _ts(5)},
        )
        self.assertEqual(plan.to_copy, [])
        self.assertEqual(plan.target_newer, ["a.pdf"])
        self.assertEqual(plan.unchanged, [])


class NestedCheckpointConflictTests(unittest.TestCase):
    def test_detects_ancestor_checkpoint(self):
        with tempfile.TemporaryDirectory() as root:
            parent = root
            child = os.path.join(root, "Note")
            os.makedirs(child)
            open(os.path.join(parent, ".sync"), "wb").close()
            conflicts = find_nested_checkpoint_conflicts(child)
            self.assertEqual(conflicts, [os.path.join(parent, ".sync")])

    def test_detects_descendant_checkpoint(self):
        with tempfile.TemporaryDirectory() as root:
            child = os.path.join(root, "Note")
            os.makedirs(child)
            open(os.path.join(child, ".sync"), "wb").close()
            conflicts = find_nested_checkpoint_conflicts(root)
            self.assertEqual(conflicts, [os.path.join(child, ".sync")])

    def test_ignores_own_checkpoint(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, ".sync"), "wb").close()
            self.assertEqual(find_nested_checkpoint_conflicts(root), [])


if __name__ == "__main__":
    unittest.main()
