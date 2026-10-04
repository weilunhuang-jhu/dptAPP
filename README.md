# Sony Digital Paper Sync

GUI to sync PDF Documents among a **Local Folder**, a Sony **Digital Paper** Device Folder, and a **Zotero Collection**.

Built on [dpt-rp1-py](https://github.com/janten/dpt-rp1-py) and [Pyzotero](https://github.com/urschrei/pyzotero).

![Main window](picture/mainwindow.png)

*Local Folder and Device Folder trees; choose a Sync Pair, then Mirror or Bidirectional Sync.*

![Zotero dialog](picture/zotero_dialog.png)

*Zotero Collections load in the background with a status line; Mirror when a collection is ready.*

## 📦 Installation

Conda (recommended):

```bash
conda create --name dpt -c conda-forge pyzotero pyqt
conda activate dpt
pip install dpt-rp1-py
```

## 🪜 Documentation

Domain vocabulary: [CONTEXT.md](CONTEXT.md). In-app: **Help → Help…**.

- [🔧️ Run the app](#run-the-app)
- [⚙️ App session config](#app-session-config)
- [📁 Sync overview](#sync-overview)
- [📚 Zotero](#zotero)
- [📡 Wi-Fi via Bluetooth (CLI)](#wi-fi-via-bluetooth-cli)

<a id="run-the-app"></a>
### 🔧️ Run the app

```bash
conda activate dpt
python dptAPP.py path_to_the_folder_to_synchronize
python dptAPP.py sync_dir/ --config config/app_config.json
```

If `config/app_config.json` exists, it loads automatically when `--config` is omitted.

<a id="app-session-config"></a>
### ⚙️ App session config

Point the app at device / Wi-Fi / Zotero library JSON so fields are prefilled. Paths are relative to the project root.

Example (`config/app_config.example.json`):

```json
{
    "device_config": "config/example_device_config.json",
    "wifi_config": "config/example_wifi_config.json",
    "library_config": "config/example_zotero_config.json"
}
```

<a id="sync-overview"></a>
### 📁 Sync overview

| Sync Pair | Modes |
|---|---|
| Local ↔ Device | Mirror Local → Device, Mirror Device → Local, Bidirectional Sync |
| Zotero → Local | Mirror Sync only |
| Zotero → Device | Mirror Sync only (Device Folder from the main window selection) |

**Mirror Sync** aligns the target with the source using modification times: copy when missing or source is newer, delete extras on the target, skip unchanged, and list target-newer Documents without overwriting them.

**Bidirectional Sync** (Local ↔ Device) uses modification times and the Local Folder Checkpoint (`.sync`) when applicable. Nested Sync Conflicts (overlapping Local Folders with Checkpoints) are warned in the GUI; you may continue or cancel.

It currently does not write into Zotero.

<a id="zotero"></a>
### 📚 Zotero

1. Open **Functions → Zotero** (library fields prefill from `library_config`).
2. **Connect** — collections load in the background; status shows progress and when fetching is done.
3. Collections show `(loading…)` until ready; Mirror is enabled only for a fully loaded selection.
4. Closing the dialog aborts an in-progress fetch.
5. Mirror Zotero → Local or → Device (PDFs come from local Zotero storage).

<a id="wi-fi-via-bluetooth-cli"></a>
### 📡 Wi-Fi via Bluetooth (CLI)

Connect the Digital Paper over Bluetooth first (address is usually `172.25.47.1`). Edit a Wi-Fi config under `config/` (see `config/wifi_*.json`): set `ssid`, `passwd`, and `security` (`psk` or `nonsec`).

```bash
dptrp1 --addr 172.25.47.1 wifi-scan
dptrp1 --addr 172.25.47.1 wifi-add path_to_wifi_config
dptrp1 --addr 172.25.47.1 wifi-list
```

Then put the device’s Wi-Fi IP into your device config (`wifi_addr`) for Connect in the GUI.

## Tests

```bash
conda activate dpt
PYTHONPATH=lib python -m unittest discover -s tests -v
```

## ToDo

- [ ] Optimize sync: reuse preview plan/listing; session-cache Zotero listing (no parallel device I/O — dpt-rp1-py uses one session)
- [ ] Bidirectional Sync GUI preview of exact file actions
- [ ] Test Synchronization with user's personal library in Zotero
