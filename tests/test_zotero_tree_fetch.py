import unittest

from zotero_tree_fetch import (
    CollectionFinished,
    CollectionStarted,
    FetchAborted,
    FetchDone,
    collection_display_name,
    is_mirror_ready,
    iter_collection_tree_events,
)


class FakeZotero:
    def __init__(self, tree):
        """
        tree: {key: {"name": str, "subs": [key...], "pdfs": [filename...]}}
        Top-level order is insertion order of keys with parent None via tops list.
        """
        self.tree = tree
        self.tops = []

    def collections_top(self):
        return [
            {
                "key": key,
                "data": {"name": self.tree[key]["name"]},
                "meta": {"numCollections": len(self.tree[key]["subs"])},
            }
            for key in self.tops
        ]

    def collections_sub(self, key):
        return [
            {
                "key": sub,
                "data": {"name": self.tree[sub]["name"]},
                "meta": {"numCollections": len(self.tree[sub]["subs"])},
            }
            for sub in self.tree[key]["subs"]
        ]

    def collection_items(self, key):
        return [
            {"data": {"filename": name}} for name in self.tree[key].get("pdfs", [])
        ]


class DisplayAndReadyTests(unittest.TestCase):
    def test_loading_suffix(self):
        self.assertEqual(
            collection_display_name("Papers", loading=True), "Papers (loading…)"
        )
        self.assertEqual(collection_display_name("Papers", loading=False), "Papers")

    def test_mirror_ready_only_when_loaded_collection(self):
        self.assertFalse(is_mirror_ready(loading=True, has_collection_key=True))
        self.assertFalse(is_mirror_ready(loading=False, has_collection_key=False))
        self.assertTrue(is_mirror_ready(loading=False, has_collection_key=True))


class IterCollectionTreeEventsTests(unittest.TestCase):
    def test_emits_started_finished_and_done_depth_first(self):
        zot = FakeZotero(
            {
                "A": {"name": "Alpha", "subs": ["B"], "pdfs": ["a.pdf"]},
                "B": {"name": "Beta", "subs": [], "pdfs": ["b.pdf", "b.pdf"]},
            }
        )
        zot.tops = ["A"]
        events = list(iter_collection_tree_events(zot, zot.collections_top()))
        kinds = [type(e) for e in events]
        self.assertEqual(
            kinds,
            [
                CollectionStarted,
                CollectionStarted,
                CollectionFinished,
                CollectionFinished,
                FetchDone,
            ],
        )
        self.assertEqual(events[0].key, "A")
        self.assertEqual(events[0].name, "Alpha")
        self.assertIsNone(events[0].parent_key)
        self.assertEqual(events[1].key, "B")
        self.assertEqual(events[1].parent_key, "A")
        self.assertEqual(events[2].key, "B")
        self.assertEqual(events[2].pdf_names, ["b.pdf"])
        self.assertEqual(events[3].key, "A")
        self.assertEqual(events[3].pdf_names, ["a.pdf"])
        self.assertEqual(events[4].top_level_count, 1)

    def test_abort_stops_further_events(self):
        zot = FakeZotero(
            {
                "A": {"name": "Alpha", "subs": [], "pdfs": ["a.pdf"]},
                "C": {"name": "Gamma", "subs": [], "pdfs": ["c.pdf"]},
            }
        )
        zot.tops = ["A", "C"]
        seen = {"n": 0}

        def should_abort():
            return seen["n"] >= 2

        events = []
        for event in iter_collection_tree_events(
            zot, zot.collections_top(), should_abort=should_abort
        ):
            events.append(event)
            seen["n"] += 1

        self.assertTrue(any(isinstance(e, CollectionStarted) for e in events))
        self.assertTrue(isinstance(events[-1], FetchAborted))
        self.assertFalse(any(isinstance(e, FetchDone) for e in events))
        self.assertFalse(any(getattr(e, "key", None) == "C" for e in events))


if __name__ == "__main__":
    unittest.main()
