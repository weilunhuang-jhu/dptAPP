# Digital Paper Sync

Vocabulary for syncing documents among a local folder, a Sony Digital Paper device, and a Zotero library.

## Language

**Sync Endpoint**:
A place that holds a folder of documents involved in sync: a Local Folder, a Device Folder, or a Zotero Collection.
_Avoid_: side, source/target as nouns for the place itself

**Sync Pair**:
Two chosen Sync Endpoints that a sync action will reconcile.
_Avoid_: mapping, link

**Mirror Sync**:
A one-way sync that aligns the target with the source using mtimes: copy when missing or source is newer, delete extras on the target, skip unchanged files, and list findings when the target Document is newer (those are not overwritten).
_Avoid_: push, overwrite, make the same (ambiguous)

**Bidirectional Sync**:
A two-way sync that reconciles both endpoints using last-modification time (and, for Local↔Device, the existing checkpoint when applicable).
_Avoid_: both-way, merge

**Local Folder**:
A directory on the computer selected for sync.
_Avoid_: sync dir (unless referring to the app's default `sync_dir/`)

**Device Folder**:
A folder path on the Digital Paper under `Document/`.
_Avoid_: DPT path, remote folder (unless speaking to the library API)

**Zotero Collection**:
A collection (and its subcollections) in a Zotero library selected for sync.
_Avoid_: Zotero folder, library (the whole library is larger than one collection)

**Document**:
A PDF file eligible for sync. Non-PDF files are ignored.
_Avoid_: file, attachment (unless speaking about Zotero's attachment item)

**Sync Mode**:
How a Sync Pair is reconciled: Mirror Sync in one direction, or Bidirectional Sync.
For this project: Local↔Device supports both directions of Mirror Sync and Bidirectional Sync; Zotero→Local and Zotero→Device support Mirror Sync only (Zotero is the source). Writing into Zotero is out of scope for now.

**Checkpoint**:
The Local Folder file `.sync` that records the last known Device Folder tree for Bidirectional Sync of that Sync Pair.
_Avoid_: cache, metadata store

**Zotero→Device Sync**:
Mirror Sync from a Zotero Collection to the Device Folder currently selected on the main window (shown in the Zotero dialog; not a second device tree).

**Nested Sync Conflict**:
A situation where the chosen Local Folder is an ancestor or descendant of another Local Folder that already has a Checkpoint (so Bidirectional Sync histories can fight). The app lists and explains these conflicts in the GUI; the user may continue or cancel.
_Avoid_: hard block (we warn and let the user decide)
