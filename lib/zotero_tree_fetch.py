"""Pure Zotero collection-tree fetch events and display helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, List, Optional, Protocol


LOADING_SUFFIX = " (loading…)"


class ZoteroCollectionsClient(Protocol):
    def collections_sub(self, key: str):
        ...

    def collection_items(self, key: str):
        ...


@dataclass(frozen=True)
class CollectionStarted:
    key: str
    name: str
    parent_key: Optional[str]


@dataclass(frozen=True)
class CollectionFinished:
    key: str
    pdf_names: List[str]


@dataclass(frozen=True)
class FetchDone:
    top_level_count: int


@dataclass(frozen=True)
class FetchAborted:
    pass


@dataclass(frozen=True)
class FetchError:
    message: str


def collection_display_name(name: str, loading: bool) -> str:
    if loading:
        return f"{name}{LOADING_SUFFIX}"
    return name


def is_mirror_ready(loading: bool, has_collection_key: bool) -> bool:
    return (not loading) and has_collection_key


def _pdf_names_in_collection(zot: ZoteroCollectionsClient, collection_key: str) -> List[str]:
    names = []
    try:
        items = zot.collection_items(collection_key)
    except Exception:
        return names
    for item in items:
        filename = item.get("data", {}).get("filename")
        if not filename or not filename.lower().endswith(".pdf"):
            continue
        if filename.startswith("."):
            continue
        names.append(filename)
    return sorted(set(names))


def iter_collection_tree_events(
    zot: ZoteroCollectionsClient,
    top_collections: Iterable[dict],
    should_abort: Optional[Callable[[], bool]] = None,
) -> Iterator[object]:
    """
    Depth-first walk: start a collection, recurse into subcollections, then
    finish with PDF names. Yields FetchAborted if should_abort becomes true.
    """
    tops = list(top_collections)

    def aborted() -> bool:
        return bool(should_abort and should_abort())

    def walk(collection: dict, parent_key: Optional[str]):
        if aborted():
            return False
        key = collection["key"]
        name = collection["data"]["name"]
        yield CollectionStarted(key=key, name=name, parent_key=parent_key)
        if aborted():
            return False

        if collection.get("meta", {}).get("numCollections", 0) > 0:
            try:
                subs = zot.collections_sub(key)
            except Exception:
                subs = []
            for sub in subs:
                ok = yield from walk(sub, parent_key=key)
                if ok is False or aborted():
                    return False

        if aborted():
            return False
        yield CollectionFinished(key=key, pdf_names=_pdf_names_in_collection(zot, key))
        return True

    for collection in tops:
        if aborted():
            yield FetchAborted()
            return
        ok = yield from walk(collection, parent_key=None)
        if ok is False or aborted():
            yield FetchAborted()
            return

    yield FetchDone(top_level_count=len(tops))
