"""Where EU5 reads the game-start setup.

Up to 1.3 the game read ``main_menu/setup/start``. Since 1.4 a bookmark (``main_menu/common/bookmarks``) names its
setup folder (``bookmark_1337 = { ... setup_folder = "setup/1337" }``) and the game reads every file in that folder,
in name order, with a mod file replacing the vanilla file of the same name. The mod writes its setup files there.

``SETUP_FOLDER`` is the active bookmark's folder. ``check_setup_folder`` compares it with the game files (the
World Builder stage calls it before writing any setup file, and a test enforces it), so a patch that moves the
setup again fails loudly instead of leaving the mod's start setup silently unread.
"""

from __future__ import annotations

from pathlib import Path

SETUP_FOLDER = "setup/1337"
SETUP_DIR = Path("main_menu") / SETUP_FOLDER
LEGACY_SETUP_DIR = Path("main_menu/setup/start")  # EU5 1.3 and earlier; not read since 1.4
BOOKMARKS_DIR = Path("main_menu/common/bookmarks")


def _setup_folders_in_file(path: Path) -> dict[str, str]:
    from eu5gameparser.clausewitz.parser import parse_file
    from eu5gameparser.clausewitz.syntax import CList

    folders: dict[str, str] = {}
    for entry in parse_file(path).entries:
        if isinstance(entry.value, CList):
            folder = next(iter(entry.value.values("setup_folder")), None)
            if folder is not None:
                folders[entry.key] = str(folder).strip('"')
    return folders


def bookmark_setup_folders(*game_dirs: Path) -> dict[str, str]:
    """bookmark key -> setup_folder, in the order the game loads them (files by name, entries in file order).

    Each of ``game_dirs`` is a layer root that holds ``main_menu`` (vanilla: ``<install>/game``, a mod: its root);
    a later layer's bookmark file replaces an earlier one of the same name."""
    by_name: dict[str, Path] = {}
    for game_dir in game_dirs:
        directory = Path(game_dir) / BOOKMARKS_DIR
        if directory.is_dir():
            by_name.update({path.name: path for path in directory.glob("*.txt")})
    folders: dict[str, str] = {}
    for name in sorted(by_name):
        folders.update(_setup_folders_in_file(by_name[name]))
    return folders


def active_setup_folder(*game_dirs: Path) -> str | None:
    """The setup folder of the bookmark a new game starts from: the first bookmark the game loads (the engine falls
    back to it when no ``-start_bookmark`` is given)."""
    return next(iter(bookmark_setup_folders(*game_dirs).values()), None)


def check_setup_folder(*game_dirs: Path) -> str:
    """Raise unless the active bookmark reads its setup from ``SETUP_FOLDER``; returns the folder."""
    folder = active_setup_folder(*game_dirs)
    if folder != SETUP_FOLDER:
        raise ValueError(
            f"the active bookmark reads its game-start setup from {folder!r}, the constructor writes {SETUP_FOLDER!r}: "
            "update SETUP_FOLDER in prosper_or_perish_constructor/setup_layout.py and move the mod's setup files"
        )
    return folder
