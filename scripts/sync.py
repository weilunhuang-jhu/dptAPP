import os
import json
from pyzotero import zotero

# mkdir
DPT_FOLDER = '../../sync_dir';
os.makedirs(DPT_FOLDER, exist_ok=True);

# def recursiveSync(top)
def createDirs(path):
    """ Make dirs with parent path and child name

    Args:
        path (str): Path of directory.

    Returns:
        No.

    """
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True);
        print(path + ' is created!')
    else:
        print(path +  ' is existed already.')


def saveFilesFromCollection(zot, folder, save_path):
    """ Copy PDF files from zotero to self-defined location

    Args:
        zot (str): zotero.Zotero.
        folder (dict): A collection in zotero.
        save_path (str): Path to save PDF files.

    Returns:
        No.

    """
    # access items in collection
    for item in zot.collection_items(folder['key']):
        # check if item is a file
        if 'filename' in item['data'].keys():
            file = item['data']['filename']
            # check if the file is .pdf 
            if '.pdf' in file:
                # TODO:check existence of file
                if not os.path.exists(os.path.join(save_path, file)):
                    print(file)
                    zot.dump(item['key'], path=save_path);


def main():

    json_path = '../user_info.json';
    with open(json_path) as json_file:
        user_info=json.load(json_file);
    lib_to_use = user_info['LibraryLumo'];

    zot = zotero.Zotero(lib_to_use['lib_id'], lib_to_use['lib_type'], lib_to_use['api_key']);
    collections = zot.collections_top();
    # TODO: make recursion to access all potential sub_collections
    for collection in collections:
        # create foler of collection in DPT folder if not exist
        collection_name = collection['data']['name'];
        collection_path_dpt =  os.path.join(DPT_FOLDER, collection_name);
        createDirs(collection_path_dpt);
        print('*******************************************')

        # access all sub_collections in collection
        if collection['meta']['numCollections'] > 0:
            for collection_sub in zot.collections_sub(collection['key']):
                collection_sub_name = collection_sub['data']['name'];
                collection_sub_path_dpt =  os.path.join(collection_path_dpt, collection_sub_name);
                createDirs(collection_sub_path_dpt);
                saveFilesFromCollection(zot, collection_sub, collection_sub_path_dpt);
        saveFilesFromCollection(zot, collection, collection_path_dpt);
        

if __name__ == "__main__":
    main()