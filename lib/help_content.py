"""Concise in-app Help text (Sync Modes + setup essentials)."""

HELP_TEXT = """\
Digital Paper Sync — Help

Sync Endpoints and Sync Pairs
• A Sync Endpoint is a Local Folder, a Device Folder (under Document/), or a Zotero Collection.
• A Sync Pair is two Sync Endpoints you choose to reconcile (click folders in the trees).

Sync Modes
• Mirror Sync (one-way): align the target with the source using modification times.
  – Copy when missing or source is newer; delete extras on the target; skip unchanged.
  – If the target Document is newer, it is listed and not overwritten.
• Bidirectional Sync (Local ↔ Device): reconcile both sides using modification times
  and the Checkpoint file (.sync) in the Local Folder when applicable.
• Nested Sync Conflict: if the Local Folder is an ancestor/descendant of another
  Local Folder that already has a Checkpoint, the app warns; you may continue or cancel.

Supported directions
• Local ↔ Device: Mirror either way, or Bidirectional Sync.
• Zotero → Local and Zotero → Device: Mirror Sync only (Zotero is the source).
  Writing into Zotero is out of scope.

Zotero
• Connect loads Zotero Collections in the background. Collections show “(loading…)”
  until ready; Mirror is enabled only for a fully loaded selection.
• Closing the Zotero dialog aborts an in-progress fetch.
• PDFs are read from your local Zotero storage for Mirror Sync.

Setup — app session config
• Prefer launching with --config pointing at an app config JSON that lists device_config,
  wifi_config, and library_config paths (relative to the project root).
• If config/app_config.json exists, it loads automatically when --config is omitted.
• Example: python dptAPP.py sync_dir/ --config config/app_config.json

Setup — device registration
• Enter serial / Wi-Fi / Bluetooth / USB addresses (or Load Device Info).
• Register once, then Connect. Refresh the Device Folder tree after connect.
• Device tree: Delete key or right-click → Delete… removes a Document or Device
  Folder (folders recursively). Confirm first; Document/ cannot be deleted.

Setup — Wi-Fi via Bluetooth (CLI)
• Connect the Digital Paper over Bluetooth (address is often 172.25.47.1).
• Edit a Wi-Fi JSON under config/ (ssid, passwd, security: psk or nonsec).
• With the dpt conda env active:
    dptrp1 --addr 172.25.47.1 wifi-scan
    dptrp1 --addr 172.25.47.1 wifi-add path_to_wifi_config
    dptrp1 --addr 172.25.47.1 wifi-list
• Put the device’s Wi-Fi IP into your device config (wifi_addr) for later Connect.

See README.md for fuller install/usage and screenshots. Domain terms: CONTEXT.md.
"""
