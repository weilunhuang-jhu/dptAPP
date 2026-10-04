import unittest

from help_content import HELP_TEXT


class HelpContentTests(unittest.TestCase):
    def test_includes_sync_modes_and_setup(self):
        self.assertIn("Sync Modes", HELP_TEXT)
        self.assertIn("Mirror Sync", HELP_TEXT)
        self.assertIn("Bidirectional Sync", HELP_TEXT)
        self.assertIn("Sync Pair", HELP_TEXT)
        self.assertIn("Zotero", HELP_TEXT)
        self.assertIn("app config", HELP_TEXT.lower())
        self.assertIn("Wi-Fi", HELP_TEXT)
        self.assertIn("Bluetooth", HELP_TEXT)
        self.assertIn("Delete", HELP_TEXT)
        self.assertIn("Document/", HELP_TEXT)


if __name__ == "__main__":
    unittest.main()
