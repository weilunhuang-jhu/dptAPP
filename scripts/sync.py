import argparse
import json
import os

from pyzotero import zotero

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DPT_FOLDER = os.path.join(SCRIPT_DIR, "..", "sync_dir")
DEFAULT_LIBRARY_CONFIG = os.path.join(
    SCRIPT_DIR, "..", "config", "example_zotero_config.json"
)


def createDirs(path):
    """Make dirs with parent path and child name."""
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
        print(path + " is created!")
    else:
        print(path + " is existed already.")


def saveFilesFromCollection(zot, folder, save_path):
    """Copy PDF files from zotero to self-defined location."""
    for item in zot.collection_items(folder["key"]):
        if "filename" in item["data"].keys():
            file = item["data"]["filename"]
            if ".pdf" in file:
                if not os.path.exists(os.path.join(save_path, file)):
                    print(file)
                    zot.dump(item["key"], path=save_path)


def main():
    parser = argparse.ArgumentParser(
        description="Copy PDFs from Zotero collections into sync_dir/."
    )
    parser.add_argument(
        "library_config",
        nargs="?",
        default=DEFAULT_LIBRARY_CONFIG,
        help="Zotero JSON with lib_id, lib_type, api_key "
        "(default: config/example_zotero_config.json)",
    )
    args = parser.parse_args()

    os.makedirs(DPT_FOLDER, exist_ok=True)

    with open(args.library_config) as json_file:
        lib_to_use = json.load(json_file)

    zot = zotero.Zotero(
        lib_to_use["lib_id"], lib_to_use["lib_type"], lib_to_use["api_key"]
    )
    collections = zot.collections_top()
    # TODO: make recursion to access all potential sub_collections
    for collection in collections:
        collection_name = collection["data"]["name"]
        collection_path_dpt = os.path.join(DPT_FOLDER, collection_name)
        createDirs(collection_path_dpt)
        print("*******************************************")

        if collection["meta"]["numCollections"] > 0:
            for collection_sub in zot.collections_sub(collection["key"]):
                collection_sub_name = collection_sub["data"]["name"]
                collection_sub_path_dpt = os.path.join(
                    collection_path_dpt, collection_sub_name
                )
                createDirs(collection_sub_path_dpt)
                saveFilesFromCollection(zot, collection_sub, collection_sub_path_dpt)
        saveFilesFromCollection(zot, collection, collection_path_dpt)


if __name__ == "__main__":
    main()
