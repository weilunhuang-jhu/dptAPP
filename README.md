# Introduction

A simple GUI to interface with Sony Digital Paper.

## Functions

* Interface with Sony Digital Paper:
    * 
    *

* Synchronize with Zotero




# Installation

### Conda environment
* conda-forge


### Dependencies

* [dpt-rp1-py](https://github.com/janten/dpt-rp1-py)
* [Pyzotero](https://github.com/urschrei/pyzotero)

### One-line installation

```
conda create --name dpt  -c conda-forge  pyzotero pyqt
```

```
pip install dpt-rp1-py
```


# ToDo

* Connect digital paper in MainWindow
* Design command in GUI to interface digital paper
* Allow user to select specific folder to synchronize with Zotero
* Test Synchronization with user's personal library in Zotero
* Recursize synchronization in Zotero, currently just support two layers of folders
* Add text label to show information in GUI (MainWindow and ZoteroDialog)
* Add help dialog in GUI