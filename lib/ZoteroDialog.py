import os
from PyQt5.QtWidgets import QDialog, QFileDialog
from PyQt5 import uic
import json
from pyzotero import zotero


self_dir = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(self_dir, "../config")
CONFIG_FILTER = "JSON files (*.json)"

class ZoteroDialog(QDialog):
    ''' Zotero dialog '''

    def __init__(self, parent, location=None, size=None):
        super().__init__()
        self.parent = parent
        ui_dlg = os.path.join(self_dir, '../ui/ZoteroDialog.ui')
        self.__ui = uic.loadUi(ui_dlg, self)
        self.zot = None # instance of zotero

        self.__ui.pushButton_loadConfig.pressed.connect(self.loadConfig)
        self.__ui.pushButton_saveConfig.pressed.connect(self.saveConfig)
        self.__ui.pushButton_syncFromZotero.pressed.connect(self.syncFromZotero)
        self.__ui.pushButton_syncToZotero.pressed.connect(self.syncToZotero)
        self.__ui.pushButton_syncBothWay.pressed.connect(self.syncBothWay)
        self.finished.connect(self.closeWindow)
        self.show()

    def getConfig(self):
        config = None
        lib_id = self.__ui.lineEdit_id.text()
        lib_type = self.__ui.lineEdit_type.text()
        api_key = self.__ui.lineEdit_key.text()
        if lib_type != '' and lib_id != '' and  api_key != '':
            config = {'lib_id':lib_id, 'lib_type':lib_type, 'api_key':api_key}
        return config


    def loadConfig(self):
        opt = QFileDialog.Options()
        opt |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(None, "Open config file (json)", directory=CONFIG_PATH , filter=CONFIG_FILTER, options=opt)
        print(file_name)
        if file_name != "":
            with open(file_name) as json_file:
                config = json.load(json_file);
            # fill in config
            self.__ui.lineEdit_id.setText(config['lib_id'])
            self.__ui.lineEdit_type.setText(config['lib_type'])
            self.__ui.lineEdit_key.setText(config['api_key'])

    def saveConfig(self):
        file_name, _ = QFileDialog.getSaveFileName(self, 'Save File', directory=CONFIG_PATH, filter=CONFIG_FILTER)
        if file_name != '' and os.path.splitext(file_name)[1] in CONFIG_FILTER:
            # get config
            lib_id = self.__ui.lineEdit_id.text()
            lib_type = self.__ui.lineEdit_type.text()
            api_key = self.__ui.lineEdit_key.text()
            config = {'lib_id':lib_id, 'lib_type':lib_type, 'api_key':api_key}
            with open(file_name, 'w') as json_file:
                json.dump(config, json_file, indent=4)

    def syncFromZotero(self):
        # check config first
        config = self.getConfig()
        if not config:
            print("Error: No config for Zotero yet.")
            return
        
        self.zot = zotero.Zotero(config['lib_id'], config['lib_type'], config['api_key'])
        collections = self.zot.collections_top()

        # TODO: make recursion to access all potential sub_collections
        for collection in collections:
            # create foler of collection in DPT folder if not exist
            collection_name = collection['data']['name']
            DPT_FOLDER = self.parent.getRootPath()
            collection_path_dpt =  os.path.join(DPT_FOLDER, collection_name)
            self.createDirs(collection_path_dpt)
            print('*******************************************')

            # access all sub_collections in collection
            if collection['meta']['numCollections'] > 0:
                for collection_sub in self.zot.collections_sub(collection['key']):
                    collection_sub_name = collection_sub['data']['name']
                    collection_sub_path_dpt =  os.path.join(collection_path_dpt, collection_sub_name)
                    self.createDirs(collection_sub_path_dpt)
                    self.saveFilesFromCollection(collection_sub, collection_sub_path_dpt)
            self.saveFilesFromCollection(collection, collection_path_dpt)

    def syncToZotero(self):
        print("Not implemented yet")

    def syncBothWay(self):
        print("Not implemented yet")
    
    def createDirs(self, path):
        """ Make dirs with parent path and child name

        Args:
            path (str): Path of directory.

        Returns:
            No.

        """
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            print(path + ' is created!')
        else:
            print(path +  ' is existed already.')


    def saveFilesFromCollection(self, folder, save_path):
        """ Copy PDF files from zotero to self-defined location

        Args:
            folder (dict): A collection in zotero.
            save_path (str): Path to save PDF files.

        Returns:
            No.

        """
        # access items in collection
        for item in self.zot.collection_items(folder['key']):
            # check if item is a file
            if 'filename' in item['data'].keys():
                file = item['data']['filename']
                # check if the file is .pdf 
                if '.pdf' in file:
                    if not os.path.exists(os.path.join(save_path, file)):
                        print(file)
                        self.zot.dump(item['key'], path=save_path)

    def closeWindow(self):
        pass