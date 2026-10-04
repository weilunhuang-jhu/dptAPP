import argparse
import os
import json
import sys

sys.path.append("lib/")

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QStandardItemModel
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMenu,
    QMessageBox,
    QShortcut,
    QTextBrowser,
    QVBoxLayout,
)

# dptrp1
from dptrp1.dptrp1 import DigitalPaper, find_auth_files, get_default_auth_files

# import from my lib
from ZoteroDialog import ZoteroDialog
from HelpDialog import HelpDialog
from app_config import load_app_config, load_json_file, wifi_summary
from device_delete import (
    apply_device_delete_ops,
    document_remote_path,
    format_device_delete_confirm,
    is_protected_device_root,
    plan_device_delete,
    should_reset_device_folder_selection,
)
from qt_trees import NODE_KIND_ROLE, PATH_ROLE, fill_folder_tree_model
from sync_service import (
    bidirectional_local_device,
    format_mirror_plan_details,
    mirror_device_to_local,
    mirror_local_to_device,
    nested_conflict_message,
)
from sync_planning import (
    device_entries_to_tree,
    device_pdf_mtimes,
    list_local_pdf_mtimes,
    plan_mirror,
)

self_dir = os.path.dirname(os.path.realpath(__file__))
ui_dir = os.path.join(self_dir, "ui")
APP_NAME = "dpt"
CONFIG_PATH = os.path.join(self_dir, "config")
CONFIG_FILTER = "JSON files (*.json)"
DEFAULT_APP_CONFIG = os.path.join(CONFIG_PATH, "app_config.json")


class dptMainwindow(QtWidgets.QMainWindow):
    def __init__(self, root_path="", app_config_path=None, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        ui_mainwindow = os.path.join(ui_dir, "MainWindow.ui")
        self.__ui = uic.loadUi(ui_mainwindow, self)
        self.dp = None
        self.device_model = QStandardItemModel(self)
        self.app_config = None
        self.library_config = None
        self.wifi_config_path = ""

        # local folder tree view
        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath(root_path)
        self.__ui.treeView.setModel(self.model)
        self.__ui.treeView.setRootIndex(self.model.index(root_path))
        self.__ui.treeView.clicked.connect(self.on_local_tree_clicked)

        # device folder tree view
        self.__ui.treeView_device.setModel(self.device_model)
        self.__ui.treeView_device.clicked.connect(self.on_device_tree_clicked)
        self.__ui.treeView_device.setContextMenuPolicy(Qt.CustomContextMenu)
        self.__ui.treeView_device.customContextMenuRequested.connect(
            self.on_device_tree_context_menu
        )
        delete_shortcut = QShortcut(
            QKeySequence.Delete, self.__ui.treeView_device
        )
        delete_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        delete_shortcut.activated.connect(self.delete_selected_device_item)

        # actions
        self.__ui.action_loadDeviceInfo.triggered.connect(self.on_mnu_loadDeviceInfo)
        self.__ui.action_saveDeviceInfo.triggered.connect(self.on_mnu_saveDeviceInfo)
        self.__ui.actionZotero.triggered.connect(self.on_mnu_Zotero)
        self.__ui.action_Help.triggered.connect(self.on_mnu_Help)

        # buttons
        self.__ui.pushButton_register.clicked.connect(self.register)
        self.__ui.pushButton_connect.clicked.connect(self.connect)
        self.__ui.pushButton_disconnect.clicked.connect(self.disconnect)
        self.__ui.pushButton_listFolders.clicked.connect(self.refresh_device_tree)
        self.__ui.pushButton_mirrorLocalToDevice.clicked.connect(
            lambda: self.run_local_device_sync("mirror_local_to_device")
        )
        self.__ui.pushButton_mirrorDeviceToLocal.clicked.connect(
            lambda: self.run_local_device_sync("mirror_device_to_local")
        )
        self.__ui.pushButton_sync.clicked.connect(
            lambda: self.run_local_device_sync("bidirectional")
        )

        # lineEdit
        self.__ui.lineEdit_syncFolderLocal.setText(root_path)
        self.__ui.lineEdit_syncFolderDPT.setText("Document/")

        self.show()
        if app_config_path:
            self.apply_app_config(app_config_path)

    def log(self, message):
        self.__ui.textBrowser.append(message)
        print(message)

    def apply_app_config(self, app_config_path):
        """Load device / wifi / library paths from an app session config."""
        try:
            self.app_config = load_app_config(app_config_path, self_dir)
        except Exception as exc:
            self.log(f"Failed to load app config {app_config_path}: {exc}")
            return

        self.log(f"Loaded app config: {self.app_config['app_config_path']}")

        device_path = self.app_config.get("device_config", "")
        if device_path:
            if self.apply_device_config_file(device_path):
                self.log(f"Loaded device config: {device_path}")
            else:
                self.log(f"Device config not found or invalid: {device_path}")

        wifi_path = self.app_config.get("wifi_config", "")
        self.wifi_config_path = wifi_path
        wifi = load_json_file(wifi_path) if wifi_path else None
        if wifi_path and wifi:
            self.log(f"Wifi config: {wifi_path} ({wifi_summary(wifi)})")
        elif wifi_path:
            self.log(f"Wifi config not found: {wifi_path}")

        library_path = self.app_config.get("library_config", "")
        library = load_json_file(library_path) if library_path else None
        if library_path and library:
            self.library_config = library
            self.log(f"Loaded library config: {library_path}")
        elif library_path:
            self.library_config = None
            self.log(f"Library config not found: {library_path}")

    def apply_device_config_file(self, file_name) -> bool:
        config = load_json_file(file_name)
        if not config:
            return False
        self.__ui.lineEdit_serial.setText(config.get("serial_id", ""))
        self.__ui.lineEdit_wifi.setText(config.get("wifi_addr", ""))
        self.__ui.lineEdit_bluetooth.setText(config.get("bluetooth_addr", ""))
        self.__ui.lineEdit_usb.setText(config.get("usb_addr", ""))
        return True

    def redact_secrets_for_display(self):
        """Mask serial/wifi and absolute paths in Status (e.g. before screenshots)."""
        # Match Bluetooth field margins so ***** starts on the first-digit column.
        l, t, r, b = self.__ui.lineEdit_bluetooth.getTextMargins()
        for edit in (self.__ui.lineEdit_serial, self.__ui.lineEdit_wifi):
            edit.setTextMargins(l, t, r, b)
            edit.setText("*****")
            edit.setCursorPosition(0)
            edit.home(False)
        plain = self.__ui.textBrowser.toPlainText()
        if not plain:
            return
        redacted = []
        for line in plain.splitlines():
            if not line.strip():
                continue
            # Keep the label; replace path/value tail after the first ": "
            if ": " in line:
                label, _, _rest = line.partition(": ")
                redacted.append(f"{label}: ******")
            else:
                redacted.append(line)
        self.__ui.textBrowser.setPlainText("\n".join(redacted))

    def get_library_config(self):
        return self.library_config

    def get_wifi_config_path(self):
        return self.wifi_config_path

    def on_mnu_loadDeviceInfo(self):
        opt = QFileDialog.Options()
        opt |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(
            None,
            "Open device info file (json)",
            directory=CONFIG_PATH,
            filter=CONFIG_FILTER,
            options=opt,
        )
        if file_name != "":
            if self.apply_device_config_file(file_name):
                self.log(f"Loaded device config: {file_name}")

    def on_mnu_saveDeviceInfo(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save File", directory=CONFIG_PATH, filter=CONFIG_FILTER
        )
        if file_name != "" and os.path.splitext(file_name)[1] in CONFIG_FILTER:
            serial_id = self.__ui.lineEdit_serial.text()
            wifi_addr = self.__ui.lineEdit_wifi.text()
            bluetooth_addr = self.__ui.lineEdit_bluetooth.text()
            usb_addr = self.__ui.lineEdit_usb.text()
            config = {
                "serial_id": serial_id,
                "wifi_addr": wifi_addr,
                "bluetooth_addr": bluetooth_addr,
                "usb_addr": usb_addr,
            }
            with open(file_name, "w") as json_file:
                json.dump(config, json_file, indent=4)

    def on_mnu_Zotero(self):
        self.zotero = ZoteroDialog(self)

    def on_mnu_Help(self):
        HelpDialog(self).exec_()

    def getRootPath(self):
        return self.model.rootPath()

    def get_selected_local_folder(self):
        return self.__ui.lineEdit_syncFolderLocal.text().strip()

    def get_selected_device_folder(self):
        return self.__ui.lineEdit_syncFolderDPT.text().strip().rstrip("/")

    def register(self):
        """Register device; user enters PIN in the terminal."""
        if not self.dp:
            dp = DigitalPaper()
            default_deviceid, default_privatekey = get_default_auth_files()
            _, key, device_id = dp.register()

            with open(default_privatekey, "w") as f:
                f.write(key)

            with open(default_deviceid, "w") as f:
                f.write(device_id)

            self.log("Finish registration")
        else:
            self.log("The device is already registered and connected")

    def connect(self):
        """Connect device. Preference: Wifi -> Bluetooth -> Serial."""
        if self.dp:
            self.log("The device is already connected")
            return

        if self.__ui.lineEdit_wifi.text() != "":
            addr = self.__ui.lineEdit_wifi.text()
            self.dp = DigitalPaper(addr=addr, assume_yes=True)
        elif self.__ui.lineEdit_bluetooth.text() != "":
            addr = self.__ui.lineEdit_bluetooth.text()
            self.dp = DigitalPaper(addr=addr, assume_yes=True)
        elif self.__ui.lineEdit_serial.text() != "":
            serial_id = self.__ui.lineEdit_serial.text()
            self.dp = DigitalPaper(id=serial_id, assume_yes=True)
        else:
            self.log("No info provided yet. Device is not connected.")
            return

        if not self.authenticate():
            self.dp = None
            self.log("Connect failed: authentication required.")
            return

        self.log("The device is successfully connected")
        self.refresh_device_tree()

    def _resolve_auth_files(self):
        """Find deviceid/privatekey, including legacy ~/.dpapp from older dpt-rp1-py."""
        found_deviceid, found_privatekey = find_auth_files()
        if os.path.exists(found_privatekey) and os.path.exists(found_deviceid):
            return found_deviceid, found_privatekey

        legacy_dir = os.path.join(os.path.expanduser("~"), ".dpapp")
        legacy_id = os.path.join(legacy_dir, "deviceid.dat")
        legacy_key = os.path.join(legacy_dir, "privatekey.dat")
        if os.path.exists(legacy_id) and os.path.exists(legacy_key):
            return legacy_id, legacy_key

        return found_deviceid, found_privatekey

    def authenticate(self):
        found_deviceid, found_privatekey = self._resolve_auth_files()
        if not os.path.exists(found_privatekey) or not os.path.exists(found_deviceid):
            self.log("Could not read device identifier and private key.")
            self.log("Please use Register in the app, or: dptrp1 --addr <addr> register")
            return False

        with open(found_deviceid) as fh:
            client_id = fh.readline().strip()
        with open(found_privatekey, "rb") as fh:
            key = fh.read()
        try:
            self.dp.authenticate(client_id, key)
        except Exception as exc:
            self.log(f"Authentication failed: {exc}")
            return False

        self.log(f"Authenticated using {found_deviceid}")
        return True

    def disconnect(self):
        if self.dp:
            self.dp = None
            self.device_model.clear()
            self.log("The device is successfully disconnected")
        else:
            self.log("The device is already disconnected")

    def on_local_tree_clicked(self, index):
        path = self.model.filePath(index)
        if os.path.isdir(path):
            self.__ui.lineEdit_syncFolderLocal.setText(path)

    def on_device_tree_clicked(self, index):
        path = index.data(PATH_ROLE)
        kind = index.data(NODE_KIND_ROLE)
        # Folder click selects that folder; Document click selects its parent folder
        if path and kind in ("folder", "document", None):
            self.__ui.lineEdit_syncFolderDPT.setText(path)

    def on_device_tree_context_menu(self, pos):
        index = self.__ui.treeView_device.indexAt(pos)
        if index.isValid():
            self.__ui.treeView_device.setCurrentIndex(index)
        menu = QMenu(self)
        action = menu.addAction("Delete…")
        action.setEnabled(self.dp is not None and index.isValid())
        action.triggered.connect(self.delete_selected_device_item)
        menu.exec_(self.__ui.treeView_device.viewport().mapToGlobal(pos))

    def _selected_device_tree_target(self):
        """Return (kind, remote_path) for the current Device tree selection, or None."""
        index = self.__ui.treeView_device.currentIndex()
        if not index.isValid():
            return None
        kind = index.data(NODE_KIND_ROLE)
        path = index.data(PATH_ROLE)
        if not path or kind not in ("folder", "document"):
            return None
        if kind == "document":
            return kind, document_remote_path(path, index.data())
        return kind, path

    def delete_selected_device_item(self):
        if not self.dp:
            self.log("Device is not connected.")
            return
        target = self._selected_device_tree_target()
        if not target:
            self.log("Select a Document or Device Folder in the Device tree first.")
            return
        kind, path = target
        if is_protected_device_root(path):
            QMessageBox.warning(
                self,
                "Delete",
                "The device root Document/ cannot be deleted.",
            )
            return

        try:
            entries = self.dp.traverse_folder("Document")
            ops = plan_device_delete(entries, kind=kind, path=path)
        except Exception as exc:
            QMessageBox.critical(self, "Delete failed", str(exc))
            self.refresh_device_tree()
            return

        detail = format_device_delete_confirm(kind=kind, path=path, ops=ops)
        if not self._confirm("Confirm Delete", detail):
            return

        try:
            apply_device_delete_ops(self.dp, ops)
            self.log(f"Deleted on device: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Delete failed", str(exc))
            self.log(f"Delete failed: {exc}")
            self._maybe_reset_device_folder_after_delete(kind, path)
            self.refresh_device_tree()
            return

        self._maybe_reset_device_folder_after_delete(kind, path)
        self.refresh_device_tree()

    def _maybe_reset_device_folder_after_delete(self, kind: str, path: str) -> None:
        if should_reset_device_folder_selection(
            self.get_selected_device_folder(),
            deleted_path=path,
            deleted_kind=kind,
        ):
            self.__ui.lineEdit_syncFolderDPT.setText("Document/")
            self.log(
                "Device Folder selection reset to Document/ "
                "(deleted path was selected or an ancestor)."
            )

    def refresh_device_tree(self):
        if not self.dp:
            self.log("Device is not connected.")
            return
        try:
            # traverse_folder falls back when the device has a large library
            entries = self.dp.traverse_folder("Document")
            tree = device_entries_to_tree(entries, root_prefix="Document")
            fill_folder_tree_model(self.device_model, tree, PATH_ROLE, header="Device")
            self.__ui.treeView_device.expandToDepth(0)
            pdf_count = sum(
                1
                for e in entries
                if e.get("entry_type") == "document"
                and str(e.get("entry_path", "")).lower().endswith(".pdf")
            )
            self.log(f"Loaded Device tree ({pdf_count} PDF Document(s)).")
        except Exception as exc:
            self.log(f"Failed to load Device Folder tree: {exc}")

    def _confirm(self, title: str, body: str) -> bool:
        """Resizable Yes/No dialog; No is the default."""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setModal(True)
        dlg.resize(560, 420)
        dlg.setMinimumSize(360, 240)

        layout = QVBoxLayout(dlg)
        text = QTextBrowser(dlg)
        text.setReadOnly(True)
        text.setPlainText(body)
        layout.addWidget(text)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Yes | QDialogButtonBox.No, parent=dlg
        )
        buttons.button(QDialogButtonBox.No).setDefault(True)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        return dlg.exec_() == QDialog.Accepted

    def run_local_device_sync(self, mode: str):
        if not self.dp:
            self.log("Device is not connected.")
            return

        local_folder = self.get_selected_local_folder()
        device_folder = self.get_selected_device_folder()
        if not local_folder or not device_folder:
            self.log("Local Folder and Device Folder cannot be empty.")
            return

        if not os.path.isdir(local_folder):
            to_create = QMessageBox.question(
                self,
                "Create Local Folder?",
                f"{local_folder} does not exist. Create it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if to_create != QMessageBox.Yes:
                self.log("Invalid local folder. Sync cancelled.")
                return
            os.makedirs(local_folder, exist_ok=True)

        conflict_msg = nested_conflict_message(local_folder)
        if conflict_msg:
            if not self._confirm("Nested Sync Conflict", conflict_msg):
                self.log("Sync cancelled (Nested Sync Conflict).")
                return

        # Preview plan for mirror modes; bidirectional uses library summary
        if mode == "mirror_local_to_device":
            entries = self.dp.traverse_folder(device_folder)
            plan = plan_mirror(
                list_local_pdf_mtimes(local_folder),
                device_pdf_mtimes(entries, device_folder),
            )
            detail = (
                f"Mirror Sync Local → Device\n"
                f"Local Folder: {local_folder}\n"
                f"Device Folder: {device_folder}\n\n"
                f"{format_mirror_plan_details(plan, delete_label='Delete on device')}"
            )
            if not self._confirm("Confirm Mirror Sync", detail):
                self.log("Sync cancelled.")
                return
            mirror_local_to_device(self.dp, local_folder, device_folder, status=self.log)
            self.refresh_device_tree()

        elif mode == "mirror_device_to_local":
            entries = self.dp.traverse_folder(device_folder)
            plan = plan_mirror(
                device_pdf_mtimes(entries, device_folder),
                list_local_pdf_mtimes(local_folder),
            )
            detail = (
                f"Mirror Sync Device → Local\n"
                f"Local Folder: {local_folder}\n"
                f"Device Folder: {device_folder}\n\n"
                f"{format_mirror_plan_details(plan, delete_label='Delete local')}"
            )
            if not self._confirm("Confirm Mirror Sync", detail):
                self.log("Sync cancelled.")
                return
            mirror_device_to_local(self.dp, local_folder, device_folder, status=self.log)

        elif mode == "bidirectional":
            detail = (
                f"Bidirectional Sync (mtime + Checkpoint)\n"
                f"Local Folder: {local_folder}\n"
                f"Device Folder: {device_folder}\n"
                f"Checkpoint: {os.path.join(local_folder, '.sync')}\n\n"
                "The dpt-rp1-py library will compute uploads, downloads, and deletes\n"
                "on both sides from mtimes and the Checkpoint, then apply them.\n"
                "A detailed file list is not shown here; Mirror Sync modes show\n"
                "exact copy/delete lists if you need a preview first."
            )
            if not self._confirm("Confirm Bidirectional Sync", detail):
                self.log("Sync cancelled.")
                return
            bidirectional_local_device(
                self.dp, local_folder, device_folder, status=self.log
            )
            self.refresh_device_tree()

        self.log("Sync finished.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Sony Digital Paper sync GUI")
    parser.add_argument(
        "sync_dir",
        nargs="?",
        default="",
        help="Local root folder shown in the Local Folder tree",
    )
    parser.add_argument(
        "--config",
        "-c",
        default=None,
        help=(
            "App session config JSON with paths to device_config, wifi_config, "
            "and library_config. Defaults to config/app_config.json when present."
        ),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    app_config_path = args.config
    if not app_config_path and os.path.isfile(DEFAULT_APP_CONFIG):
        app_config_path = DEFAULT_APP_CONFIG

    app = QtWidgets.QApplication(sys.argv)
    dpt_window = dptMainwindow(
        root_path=args.sync_dir, app_config_path=app_config_path
    )
    dpt_window.show()
    sys.exit(app.exec_())
