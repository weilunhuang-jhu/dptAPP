import os
import json

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
    QTextBrowser,
    QVBoxLayout,
)
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5 import uic
from pyzotero import zotero

from qt_trees import NODE_KIND_ROLE, PATH_ROLE
from sync_planning import device_pdf_mtimes, list_local_pdf_mtimes, plan_mirror
from sync_service import (
    collect_zotero_pdfs,
    file_mtimes,
    format_mirror_plan_details,
    mirror_zotero_to_device,
    mirror_zotero_to_local,
    nested_conflict_message,
)
from zotero_tree_fetch import (
    CollectionFinished,
    CollectionStarted,
    FetchAborted,
    FetchDone,
    FetchError,
    collection_display_name,
    is_mirror_ready,
    iter_collection_tree_events,
)

self_dir = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(self_dir, "../config")
CONFIG_FILTER = "JSON files (*.json)"
ZOTERO_STORAGE_HOME = "/home/weilunhuang/Zotero/storage"
COLLECTION_KEY_ROLE = 258
LOADING_ROLE = 259
BASE_NAME_ROLE = 260


class _ZoteroTreeFetchThread(QThread):
    event = pyqtSignal(object)

    def __init__(self, zot, parent=None):
        super().__init__(parent)
        self._zot = zot
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            tops = self._zot.collections_top()
            for ev in iter_collection_tree_events(
                self._zot, tops, should_abort=lambda: self._abort
            ):
                self.event.emit(ev)
                if isinstance(ev, (FetchAborted, FetchDone, FetchError)):
                    break
        except Exception as exc:
            self.event.emit(FetchError(message=str(exc)))


class ZoteroDialog(QDialog):
    """Zotero dialog"""

    def __init__(self, parent, location=None, size=None):
        super().__init__()
        self.parent = parent
        ui_dlg = os.path.join(self_dir, "../ui/ZoteroDialog.ui")
        self.__ui = uic.loadUi(ui_dlg, self)
        self.zot = None
        self.selected_collection_key = None
        self.collection_model = QStandardItemModel(self)
        self.__ui.treeView_zotero.setModel(self.collection_model)
        self.__ui.treeView_zotero.clicked.connect(self.on_collection_clicked)
        self._items_by_key = {}
        self._fetch_thread = None
        self._fetch_generation = 0

        self.__ui.pushButton_loadConfig.pressed.connect(self.loadConfig)
        self.__ui.pushButton_saveConfig.pressed.connect(self.saveConfig)
        self.__ui.pushButton_connect.pressed.connect(self.connect_zotero)
        self.__ui.pushButton_mirrorToLocal.pressed.connect(self.mirror_to_local)
        self.__ui.pushButton_mirrorToDevice.pressed.connect(self.mirror_to_device)
        self.finished.connect(self.closeWindow)

        self.__ui.lineEdit_localFolder.setText(
            self.parent.get_selected_local_folder() or self.parent.getRootPath()
        )
        self.__ui.lineEdit_deviceFolder.setText(self.parent.get_selected_device_folder())

        library = None
        if hasattr(self.parent, "get_library_config"):
            library = self.parent.get_library_config()
        if library:
            self.apply_library_config(library)

        self._set_status("Status: Idle")
        self._update_mirror_enabled()
        self.show()

    def apply_library_config(self, config):
        self.__ui.lineEdit_id.setText(config.get("lib_id", ""))
        self.__ui.lineEdit_type.setText(config.get("lib_type", ""))
        self.__ui.lineEdit_key.setText(config.get("api_key", ""))

    def getConfig(self):
        config = None
        lib_id = self.__ui.lineEdit_id.text()
        lib_type = self.__ui.lineEdit_type.text()
        api_key = self.__ui.lineEdit_key.text()
        if lib_type != "" and lib_id != "" and api_key != "":
            config = {"lib_id": lib_id, "lib_type": lib_type, "api_key": api_key}
        return config

    def loadConfig(self):
        opt = QFileDialog.Options()
        opt |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(
            None,
            "Open config file (json)",
            directory=CONFIG_PATH,
            filter=CONFIG_FILTER,
            options=opt,
        )
        if file_name != "":
            with open(file_name) as json_file:
                config = json.load(json_file)
            self.apply_library_config(config)
            if hasattr(self.parent, "library_config"):
                self.parent.library_config = config

    def saveConfig(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save File", directory=CONFIG_PATH, filter=CONFIG_FILTER
        )
        if file_name != "" and os.path.splitext(file_name)[1] in CONFIG_FILTER:
            lib_id = self.__ui.lineEdit_id.text()
            lib_type = self.__ui.lineEdit_type.text()
            api_key = self.__ui.lineEdit_key.text()
            config = {"lib_id": lib_id, "lib_type": lib_type, "api_key": api_key}
            with open(file_name, "w") as json_file:
                json.dump(config, json_file, indent=4)

    def _set_status(self, message: str):
        self.__ui.label_status.setText(message)

    def redact_secrets_for_display(self):
        """Mask library id and API key in the form (e.g. before screenshots)."""
        # Match Type field margins so ****** starts on the first-character column.
        l, t, r, b = self.__ui.lineEdit_type.getTextMargins()
        for edit in (self.__ui.lineEdit_id, self.__ui.lineEdit_key):
            if edit.text():
                edit.setTextMargins(l, t, r, b)
                edit.setText("******")
                edit.setCursorPosition(0)
                edit.home(False)

    def _update_mirror_enabled(self):
        loading = False
        if self.selected_collection_key:
            item = self._items_by_key.get(self.selected_collection_key)
            if item is not None:
                loading = bool(item.data(LOADING_ROLE))
        ready = is_mirror_ready(
            loading=loading, has_collection_key=bool(self.selected_collection_key)
        )
        self.__ui.pushButton_mirrorToLocal.setEnabled(ready)
        self.__ui.pushButton_mirrorToDevice.setEnabled(ready)

    def _request_abort_fetch(self):
        """Ask the worker to stop; never block the UI thread with wait()."""
        thread = self._fetch_thread
        if thread is None:
            return
        self._fetch_generation += 1
        thread.abort()
        try:
            thread.event.disconnect()
        except TypeError:
            pass
        self._fetch_thread = None

    def connect_zotero(self):
        config = self.getConfig()
        if not config:
            QMessageBox.warning(self, "Zotero", "Load or enter Zotero config first.")
            return
        try:
            self.zot = zotero.Zotero(
                config["lib_id"], config["lib_type"], config["api_key"]
            )
        except Exception as exc:
            QMessageBox.critical(self, "Zotero Connect failed", str(exc))
            self.zot = None
            return

        self._request_abort_fetch()
        self._fetch_generation += 1
        generation = self._fetch_generation
        self._items_by_key.clear()
        self.selected_collection_key = None
        self.__ui.lineEdit_collection.clear()
        self.collection_model.clear()
        self.collection_model.setHorizontalHeaderLabels(["Zotero"])
        self.__ui.lineEdit_deviceFolder.setText(self.parent.get_selected_device_folder())
        self._set_status("Status: Fetching Zotero collections… updating tree…")
        self._update_mirror_enabled()

        # Unparented so dialog close does not destroy a running QThread
        thread = _ZoteroTreeFetchThread(self.zot)
        thread.event.connect(
            lambda ev, gen=generation: self._on_fetch_event(ev, gen)
        )
        thread.finished.connect(
            lambda thr=thread: self._on_fetch_thread_finished(thr)
        )
        thread.finished.connect(thread.deleteLater)
        self._fetch_thread = thread
        thread.start()

    def _on_fetch_thread_finished(self, thread):
        if self._fetch_thread is thread:
            self._fetch_thread = None

    def _on_fetch_event(self, event, generation: int):
        if generation != self._fetch_generation:
            return
        if isinstance(event, CollectionStarted):
            item = QStandardItem(
                collection_display_name(event.name, loading=True)
            )
            item.setEditable(False)
            item.setData(event.key, COLLECTION_KEY_ROLE)
            item.setData(event.name, BASE_NAME_ROLE)
            item.setData(event.name, PATH_ROLE)
            item.setData("collection", NODE_KIND_ROLE)
            item.setData(True, LOADING_ROLE)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            if event.parent_key and event.parent_key in self._items_by_key:
                self._items_by_key[event.parent_key].appendRow(item)
            else:
                self.collection_model.invisibleRootItem().appendRow(item)
            self._items_by_key[event.key] = item
            self.__ui.treeView_zotero.expandToDepth(0)
            return

        if isinstance(event, CollectionFinished):
            item = self._items_by_key.get(event.key)
            if item is None:
                return
            base = item.data(BASE_NAME_ROLE) or item.text()
            item.setText(collection_display_name(base, loading=False))
            item.setData(False, LOADING_ROLE)
            item.setFlags(item.flags() | Qt.ItemIsSelectable)
            for filename in event.pdf_names:
                pdf_item = QStandardItem(filename)
                pdf_item.setEditable(False)
                pdf_item.setData(event.key, COLLECTION_KEY_ROLE)
                pdf_item.setData(filename, PATH_ROLE)
                pdf_item.setData("document", NODE_KIND_ROLE)
                pdf_item.setData(False, LOADING_ROLE)
                item.appendRow(pdf_item)
            if self.selected_collection_key == event.key:
                self._update_mirror_enabled()
            return

        if isinstance(event, FetchDone):
            self._set_status(
                f"Status: Fetching done. Loaded {event.top_level_count} "
                "top-level collection(s)."
            )
            self._update_mirror_enabled()
            return

        if isinstance(event, FetchAborted):
            self._set_status("Status: Fetch aborted.")
            return

        if isinstance(event, FetchError):
            self._set_status(f"Status: Fetch failed — {event.message}")
            QMessageBox.critical(self, "Zotero Connect failed", event.message)
            self.zot = None

    def on_collection_clicked(self, index):
        kind = index.data(NODE_KIND_ROLE)
        key = index.data(COLLECTION_KEY_ROLE)
        if not key:
            return

        loading = bool(index.data(LOADING_ROLE))
        if kind == "collection" and loading:
            # Incomplete nodes are not selectable for Mirror; keep fetch status line
            self.selected_collection_key = None
            self.__ui.lineEdit_collection.clear()
            self._update_mirror_enabled()
            return

        names = []
        cur = index
        while cur.isValid():
            if cur.data(NODE_KIND_ROLE) != "document":
                base = cur.data(BASE_NAME_ROLE) or cur.data()
                # Strip loading suffix if present on ancestors mid-fetch
                text = base
                names.append(text)
            cur = cur.parent()
        path = "/".join(reversed(names))
        self.selected_collection_key = key
        self.__ui.lineEdit_collection.setText(path)
        self.__ui.lineEdit_deviceFolder.setText(self.parent.get_selected_device_folder())
        self._update_mirror_enabled()
        if kind == "document":
            self.parent.log(
                f"Selected Document in Zotero Collection: {path}/{index.data()}"
            )

    def _confirm(self, title, body) -> bool:
        """Resizable Yes/No dialog so long source/target comparisons stay usable."""
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

    def _selection_ready_for_mirror(self) -> bool:
        if not self.zot or not self.selected_collection_key:
            return False
        item = self._items_by_key.get(self.selected_collection_key)
        loading = bool(item.data(LOADING_ROLE)) if item is not None else False
        return is_mirror_ready(
            loading=loading, has_collection_key=bool(self.selected_collection_key)
        )

    def mirror_to_local(self):
        if not self._selection_ready_for_mirror():
            QMessageBox.warning(
                self,
                "Zotero",
                "Connect and select a fully loaded Zotero Collection first.",
            )
            return
        local_folder = self.__ui.lineEdit_localFolder.text().strip()
        if not local_folder:
            QMessageBox.warning(self, "Zotero", "Local Folder cannot be empty.")
            return

        conflict_msg = nested_conflict_message(local_folder)
        if conflict_msg and not self._confirm("Nested Sync Conflict", conflict_msg):
            return

        pairs = collect_zotero_pdfs(
            self.zot, self.selected_collection_key, ZOTERO_STORAGE_HOME
        )
        src_by_rel = {rel: src for rel, src in pairs}
        plan = plan_mirror(file_mtimes(src_by_rel), list_local_pdf_mtimes(local_folder))
        detail = (
            f"Mirror Sync Zotero → Local\n"
            f"Collection: {self.__ui.lineEdit_collection.text()}\n"
            f"Local Folder: {local_folder}\n\n"
            f"{format_mirror_plan_details(plan, delete_label='Delete local')}"
        )
        if not self._confirm("Confirm Mirror Sync", detail):
            return
        mirror_zotero_to_local(
            self.zot,
            self.selected_collection_key,
            local_folder,
            ZOTERO_STORAGE_HOME,
            status=self.parent.log,
        )
        self.parent.log("Finished Mirror Zotero → Local")

    def mirror_to_device(self):
        if not self._selection_ready_for_mirror():
            QMessageBox.warning(
                self,
                "Zotero",
                "Connect and select a fully loaded Zotero Collection first.",
            )
            return
        if not self.parent.dp:
            QMessageBox.warning(
                self, "Zotero", "Connect the device on the main window first."
            )
            return

        device_folder = self.parent.get_selected_device_folder()
        self.__ui.lineEdit_deviceFolder.setText(device_folder)
        if not device_folder:
            QMessageBox.warning(
                self, "Zotero", "Select a Device Folder on the main window first."
            )
            return

        pairs = collect_zotero_pdfs(
            self.zot, self.selected_collection_key, ZOTERO_STORAGE_HOME
        )
        src_by_rel = {rel: src for rel, src in pairs}
        entries = self.parent.dp.traverse_folder(device_folder)
        plan = plan_mirror(
            file_mtimes(src_by_rel), device_pdf_mtimes(entries, device_folder)
        )
        detail = (
            f"Mirror Sync Zotero → Device\n"
            f"Collection: {self.__ui.lineEdit_collection.text()}\n"
            f"Device Folder: {device_folder}\n\n"
            f"{format_mirror_plan_details(plan, delete_label='Delete on device')}"
        )
        if not self._confirm("Confirm Mirror Sync", detail):
            return
        mirror_zotero_to_device(
            self.zot,
            self.parent.dp,
            self.selected_collection_key,
            device_folder,
            ZOTERO_STORAGE_HOME,
            status=self.parent.log,
        )
        self.parent.refresh_device_tree()
        self.parent.log("Finished Mirror Zotero → Device")

    def closeEvent(self, event):
        self._request_abort_fetch()
        super().closeEvent(event)

    def closeWindow(self):
        self._request_abort_fetch()
