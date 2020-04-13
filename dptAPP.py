import os
import sys
sys.path.append("lib/")

from PyQt5 import QtCore, QtWidgets, uic

# import from my lib
from ZoteroDialog import ZoteroDialog

self_dir = os.path.dirname(os.path.realpath(__file__))
ui_dir = os.path.join(self_dir, 'ui')
APP_NAME = "dpt"


class dptMainwindow(QtWidgets.QMainWindow):
    def __init__(self, root_path="", parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        ui_mainwindow = os.path.join(ui_dir, 'MainWindow.ui')
        self.__ui = uic.loadUi(ui_mainwindow, self)

        # folder tree view
        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath(root_path)
        self.__ui.treeView.setModel(self.model)
        self.__ui.treeView.setRootIndex(self.model.index(root_path))

        # actions
        self.__ui.actionZotero.triggered.connect(self.on_mnu_Zotero)

        self.show()

    def on_mnu_Zotero(self):
        self.zotero = ZoteroDialog(self)

    def getRootPath(self):
        return self.model.rootPath()

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