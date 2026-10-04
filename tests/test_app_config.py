import json
import os
import tempfile
import unittest

from app_config import load_app_config, resolve_path, wifi_summary


class AppConfigTests(unittest.TestCase):
    def test_resolve_relative_and_absolute(self):
        self.assertTrue(resolve_path("config/x.json", "/proj").endswith("config/x.json"))
        self.assertEqual(resolve_path("/abs/x.json", "/proj"), "/abs/x.json")

    def test_load_app_config_resolves_paths(self):
        with tempfile.TemporaryDirectory() as root:
            cfg_path = os.path.join(root, "app.json")
            with open(cfg_path, "w") as fh:
                json.dump(
                    {
                        "device_config": "config/device.json",
                        "wifi_config": "config/wifi.json",
                        "library_config": "config/lib.json",
                    },
                    fh,
                )
            loaded = load_app_config(cfg_path, root)
            self.assertEqual(
                loaded["device_config"], os.path.join(root, "config/device.json")
            )
            self.assertEqual(
                loaded["wifi_config"], os.path.join(root, "config/wifi.json")
            )
            self.assertEqual(
                loaded["library_config"], os.path.join(root, "config/lib.json")
            )

    def test_wifi_summary(self):
        self.assertIn("ssid='Home'", wifi_summary({"ssid": "Home", "security": "psk"}))


if __name__ == "__main__":
    unittest.main()
