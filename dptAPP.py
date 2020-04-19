import os
import json
import sys
sys.path.append("lib/")

from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtWidgets import QDialog, QFileDialog

# dptrp1
from dptrp1.dptrp1 import DigitalPaper, find_auth_files, get_default_auth_files

# import from my lib
from ZoteroDialog import ZoteroDialog

self_dir = os.path.dirname(os.path.realpath(__file__))
ui_dir = os.path.join(self_dir, 'ui')
APP_NAME = "dpt"
CONFIG_PATH = os.path.join(self_dir, "config")
CONFIG_FILTER = "JSON files (*.json)"


class dptMainwindow(QtWidgets.QMainWindow):
    def __init__(self, root_path="", parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        ui_mainwindow = os.path.join(ui_dir, 'MainWindow.ui')
        self.__ui = uic.loadUi(ui_mainwindow, self)
        self.dp = None

        # folder tree view
        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath(root_path)
        self.__ui.treeView.setModel(self.model)
        self.__ui.treeView.setRootIndex(self.model.index(root_path))
        self.__ui.treeView.expanded.connect(self.setSyncFolderDPT)

        # actions
        self.__ui.action_loadDeviceInfo.triggered.connect(self.on_mnu_loadDeviceInfo)
        self.__ui.action_saveDeviceInfo.triggered.connect(self.on_mnu_saveDeviceInfo)
        self.__ui.actionZotero.triggered.connect(self.on_mnu_Zotero)

        # buttons
        self.__ui.pushButton_register.clicked.connect(self.register)
        self.__ui.pushButton_connect.clicked.connect(self.connect)
        self.__ui.pushButton_disconnect.clicked.connect(self.disconnect)
        self.__ui.pushButton_listFolders.clicked.connect(self.listFolders)
        self.__ui.pushButton_sync.clicked.connect(self.sync)

        # lineEdit
        self.__ui.lineEdit_syncFolderLocal.setText(root_path) 
        self.__ui.lineEdit_syncFolderDPT.setText('Document/')

        self.show()

    def on_mnu_loadDeviceInfo(self):
        opt = QFileDialog.Options()
        opt |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(None, "Open device info file (json)", directory=CONFIG_PATH , filter=CONFIG_FILTER, options=opt)
        if file_name != "":
            with open(file_name) as json_file:
                config = json.load(json_file)
            # fill in config
            self.__ui.lineEdit_serial.setText(config['serial_id'])
            self.__ui.lineEdit_wifi.setText(config['wifi_addr'])
            self.__ui.lineEdit_bluetooth.setText(config['bluetooth_addr'])
            self.__ui.lineEdit_usb.setText(config['usb_addr'])

    def on_mnu_saveDeviceInfo(self):
        file_name, _ = QFileDialog.getSaveFileName(self, 'Save File', directory=CONFIG_PATH, filter=CONFIG_FILTER)
        if file_name != '' and os.path.splitext(file_name)[1] in CONFIG_FILTER:
            # get config
            serial_id = self.__ui.lineEdit_serial.text()
            wifi_addr = self.__ui.lineEdit_wifi.text()
            bluetooth_addr = self.__ui.lineEdit_bluetooth.text()
            usb_addr = self.__ui.lineEdit_usb.text()
            config = {'serial_id':serial_id, 'wifi_addr':wifi_addr,\
                      'bluetooth_addr':bluetooth_addr, 'usb_addr':usb_addr}
            with open(file_name, 'w') as json_file:
                json.dump(config, json_file, indent=4)

    def on_mnu_Zotero(self):
        self.zotero = ZoteroDialog(self)

    def getRootPath(self):
        return self.model.rootPath()

    def register(self):
        """ Register device, note the user needs to key in pin code in terminal now.
        """
        if not self.dp:
            dp = DigitalPaper()
            # When registering the device, we default to storing auth files in our own configuration directory
            default_deviceid, default_privatekey = get_default_auth_files()
            _, key, device_id = dp.register()

            with open(default_privatekey, "w") as f:
                f.write(key)

            with open(default_deviceid, "w") as f:
                f.write(device_id)

            status_info = "Finish registration"
            print(status_info)

        else:

            status_info = "The divice is already registered and connected"
            print(status_info)

    def connect(self):
        """ Connect device with provided info. Follow the order below if more than
        one info are provided:

        Wifi -> Bluetooth -> Serial
        !!! Note that USB is not supported yet

        """
        # do nothing if the device is connected before
        if self.dp:
            status_info = "The device is already connected"
            print(status_info)
            return 

        if self.__ui.lineEdit_wifi.text() != '' :
            addr = self.__ui.lineEdit_wifi.text()
            self.dp = DigitalPaper(addr=addr)

        elif self.__ui.lineEdit_bluetooth.text()!= '' :
            addr = self.__ui.lineEdit_bluetooth.text()
            self.dp = DigitalPaper(addr=addr)
        
        elif self.__ui.lineEdit_serial.text() != '':
            serial_id = self.__ui.lineEdit_serial.text()
            self.dp = DigitalPaper(id=serial_id)

        else:
            status_info = "No info provided yet. Device is not connected. "
            print(status_info)
            return
        
        # authenticate if one of the info is provided
        self.authenticate()
        status_info = "The device is successfully connected"
        print(status_info)

    def authenticate(self):
        found_deviceid, found_privatekey = find_auth_files()
        if not os.path.exists(found_privatekey) or not os.path.exists(found_deviceid):
            print("Could not read device identifier and private key.")
            print("Please use command 'register' first:")
            return

        with open(found_deviceid) as fh:
            client_id = fh.readline().strip()
        with open(found_privatekey, "rb") as fh:
            key = fh.read()
        self.dp.authenticate(client_id, key)

    def disconnect(self):
        if self.dp:
            self.dp = None
            status_info = "The device is successfully disconnected"
            print(status_info)

        else:
            status_info = "The device is already disconnected"
            print(status_info)

    def setSyncFolderDPT(self, index):
        self.__ui.lineEdit_syncFolderLocal.setText(self.model.filePath(index)) 

    def listFolders(self):
        data =  self.dp.list_all()
        for d in data:
            if d["entry_type"] == "folder":
                    print(d["entry_path"] + "/")

    def sync(self):
        local_folder = self.__ui.lineEdit_syncFolderLocal.text()
        dpt_folder = self.__ui.lineEdit_syncFolderDPT.text()
        # check empty
        if local_folder == '' or dpt_folder == '':
            status_info = "Local folder and DPT folder cannot be empty"
            print(status_info)
            return
        # check existence
        if not os.path.isdir(local_folder):
            to_create = input('Local folder does not exist, create new folder?(y/n)')
            if to_create.lower() == 'y':
                os.makedirs(local_folder, exist_ok=True)
                print(local_folder + ' is created!')
            else:
                print("Invalid local folder. Device is not synchronized.")
                return

        self.dp.sync(local_folder, dpt_folder)
        


if __name__ == '__main__':
  app = QtWidgets.QApplication(sys.argv)
  # check if root path is provided
  root_path = ""
  assert len(sys.argv) < 3, "At most one argument to define your root folder!"
  if len(sys.argv) == 2:
      root_path = sys.argv[-1]
  dpt_window = dptMainwindow(root_path=root_path)
  dpt_window.show()
  sys.exit(app.exec_())