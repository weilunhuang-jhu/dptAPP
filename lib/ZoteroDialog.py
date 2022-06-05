import os
import glob
import shutil
from PyQt5.QtWidgets import QDialog, QFileDialog
from PyQt5 import uic
import json
from pyzotero import zotero


self_dir = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(self_dir, "../config")
CONFIG_FILTER = "JSON files (*.json)"
ZOTERO_STORAGE_HOME = "/home/weilunhuang/Zotero/storage"

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

        # make recursion to access all potential sub_collections
        DPT_FOLDER = self.parent.getRootPath()
        for collection in collections:
            self.syncFromZoteroRecursively(collection, DPT_FOLDER)

        print("Finished Sync From Zotero")

    def syncToZotero(self):
        print("Not implemented yet")

    def syncBothWay(self):
        print("Not implemented yet")
    
    def createDirs(self, path):
        """ Make dirs with parent path and child name

        Args:
            path (str): Path of directory.

        Returns:
            A boolean variable showing if the Dir is newly created. 

        """
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            print(path + ' is created!')
            return True
        else:
            print(path +  ' is existed already.')
            return False


    def syncFromZoteroRecursively(self, collection, parent_path):
        """ Synchronize files from collection of zotero recursively.
            Copy files from Zotero and delete files that are not in Zotero.

        Args:
            collection (dict): A collection in zotero.
            parent_path (str): Path of parent folder.

        Returns:
            No.

        """

        # create foler of collection in DPT folder if not exist
        collection_name = collection['data']['name']
        collection_path_dpt =  os.path.join(parent_path, collection_name)
        is_new_dir = self.createDirs(collection_path_dpt)
        files_in_zotero = self.saveFilesFromCollection(collection, collection_path_dpt)
        # delete excessive local files if the local folder exists before
        if not is_new_dir:
            self.deleteFilesFromCollection(files_in_zotero, collection_path_dpt)
        print('*******************************************')
        print(collection_path_dpt)
        if collection['meta']['numCollections'] > 0:
            for collection_sub in self.zot.collections_sub(collection['key']):
                self.syncFromZoteroRecursively(collection_sub, collection_path_dpt)
        
    def saveFilesFromCollection(self, folder, save_path):
        """ Copy PDF files from zotero to self-defined location

        Args:
            folder (dict): A collection in zotero.
            save_path (str): Path to save PDF files.

        Returns:
            files: list of pdf files in the collection

        """
        # TODO: consider using set for files to speed up
        files = []
        # access items in collection
        for item in self.zot.collection_items(folder['key']):

            # check if item is a file
            if 'filename' not in item['data'].keys():
                continue
            file = item['data']['filename']
            # check if the file is .pdf 
            if '.pdf' not in file:
                continue
            files.append(file)
            # check if the file exists already or not 
            dest_fname = os.path.join(save_path, file)
            if not os.path.exists(dest_fname):
                # # copy from zotero
                # self.zot.dump(item['key'], path=save_path)

                # copy from local storage
                src_fname = os.path.join(ZOTERO_STORAGE_HOME, item['key'], file)
                shutil.copy(src_fname, dest_fname)
                print(file + "  is added.")

        return files

    def deleteFilesFromCollection(self, collection_files, local_path):
        """ Delete local PDF files that are not in Zotero.

        Args:
            collection_files: list of pdf files in current collection
            local_path (str): Path to local folder.

        Returns:
            No.

        """

        # TODO: cached files that are newly created, take sets difference
        # to delete excessive files
        local_files = glob.glob(os.path.join(local_path, "*.pdf"))
        for file in local_files:
            file_name = os.path.split(file)[-1]
            if file_name not in collection_files:
                os.remove(file)
                print(file_name + " is removed.")

    def closeWindow(self):
        pass