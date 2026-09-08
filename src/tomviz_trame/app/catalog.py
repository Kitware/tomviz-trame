"""The catalog: the node definitions the user can add to a pipeline.

Each entry is a JSON description plus a Python script, found by scanning
directories: the upstream ``Name.json`` + ``Name.py`` sidecar pairs, or a
single ``name.py`` exposing a module-level ``JSON`` dict. Today every entry
is a transform (the desktop app calls them operators); schema-v2 source
kernels will land in the same catalog.

Configuration lives in ``~/.tomviz/catalog.json`` (or ``--catalog``): the
directories and Python modules to scan, and the user's favorites. The
builtin module is always scanned. An older ``operators.json`` is read when
no ``catalog.json`` exists yet."""

import importlib
import importlib.util
import json
from pathlib import Path

from loguru import logger
from trame.app import TrameComponent
from trame.decorators import controller

from tomviz_trame.app import data_model

__all__ = [
    "Catalog",
    "CatalogEntry",
]

DEFAULT_CONFIG = Path.home() / ".tomviz" / "catalog.json"
LEGACY_CONFIG = Path.home() / ".tomviz" / "operators.json"

DEFAULT_MODULES = [
    "tomviz.operators.builtin",
]
DEFAULT_DIRECTORIES = [
    (Path.home() / ".tomviz" / "catalog"),
]


def module_to_path(module_name):
    loaded_module = importlib.import_module(module_name)
    module_path = Path(loaded_module.__file__)
    if module_path.is_file():
        return str(module_path.parent.resolve())
    return str(module_path.resolve())


def extract_entry_from_py(module_path: Path):
    name = module_path.name
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.JSON, module_path, module


class CatalogEntry:
    """A definition (``json``) and the script implementing it (``file``)."""

    def __init__(self, json_content, py_file, module):
        self.json = json_content
        self.file = py_file
        self.module = module

    @property
    def name(self):
        return self.json.get("name", "unnamed")

    @property
    def label(self):
        return self.json.get("label", "Un-Named")

    @property
    def tags(self):
        return self.json.get("tags", [])

    @property
    def icon(self):
        return self.json.get("icon", "mdi-calculator-variant-outline")

    @property
    def path(self):
        return tuple(self.json.get("path", []))

    def to_item(self, server, favorites):
        return data_model.CatalogItem(
            server,
            title=self.label,
            name=self.name,
            tags=self.tags,
            icon=self.icon,
            favorite=self.name in favorites,
            meta=self.json,
        )


class Catalog(TrameComponent):
    def __init__(self, server=None, config_file=None, read_only=False):
        super().__init__(server)
        self.read_only = read_only
        self.favorites = set()
        self.directories = set()
        self.modules = set()
        self.entries: dict[str, CatalogEntry] = {}
        self.entry_files = set()
        self.root = data_model.CatalogFolder(self.server)

        if config_file is None:
            self.config_file = DEFAULT_CONFIG
            source = self._default_config_source()
        else:
            self.config_file = Path(config_file)
            if not self.config_file.exists():
                msg = f"Invalid path to config: {config_file}"
                raise ValueError(msg)
            source = self.config_file

        if source is not None:
            config = json.loads(source.read_text())
            self.directories.update(config.get("directories", []))
            self.modules.update(config.get("modules", []))
            self.favorites.update(config.get("favorites", []))
        self.state.catalog_favorite_count = len(self.favorites)
        self.update()

    def _default_config_source(self) -> Path | None:
        """The config file to read when none was given: ``catalog.json``, an
        older ``operators.json``, or a freshly written default."""
        if DEFAULT_CONFIG.exists():
            return DEFAULT_CONFIG
        if LEGACY_CONFIG.exists():
            logger.info(
                "Reading the catalog configuration from {}; it will be saved as {}",
                LEGACY_CONFIG,
                DEFAULT_CONFIG,
            )
            return LEGACY_CONFIG
        self.add_defaults()
        self.save()
        return DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else None

    @controller.set("update_favorite")
    def update_favorite(self, name, favorite):
        if favorite:
            self.favorites.add(name)
        else:
            self.favorites.discard(name)

        with self.state as s:
            s.catalog_favorite_count = len(self.favorites)

        self.save()

    def add_defaults(self):
        for module_name in DEFAULT_MODULES:
            self.add_module(module_name)
        for directory in DEFAULT_DIRECTORIES:
            self.add_directory(directory)

    def clear(self):
        self.directories.clear()
        self.modules.clear()

    def add_directory(self, directory: str | Path):
        self.directories.add(str(Path(directory).resolve()))

    def remove_directory(self, directory: str | Path):
        self.directories.discard(str(Path(directory).resolve()))

    def add_module(self, module_name: str):
        self.modules.add(module_name)

    def remove_module(self, module_name: str):
        self.modules.discard(module_name)

    def save(self):
        if self.read_only:
            return

        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(
            json.dumps(
                {
                    "directories": list(self.directories),
                    "modules": list(self.modules),
                    "favorites": list(self.favorites),
                },
                indent=2,
            )
        )

    def update(self):
        self.entries.clear()
        # The builtin entries ship with the app and are always available,
        # whatever the config file lists (older config files predate them).
        module_paths = []
        for module_name in {*DEFAULT_MODULES, *self.modules}:
            try:
                module_paths.append(module_to_path(module_name))
            except ImportError:
                logger.warning("Cannot import catalog module {}", module_name)
        all_directories = map(Path, [*self.directories, *module_paths])
        for directory in all_directories:
            if not directory.exists():
                logger.warning("Catalog directory not found: {}", directory)
                continue

            # search json first
            for file_json in directory.glob("*.json"):
                file_py = file_json.with_suffix(".py")
                if file_py.exists():
                    try:
                        json_content = json.loads(file_json.read_text())
                        self._register(json_content, file_py)
                    except json.decoder.JSONDecodeError:
                        self.entry_files.add(file_py)
                        logger.warning("Invalid catalog entry {}", file_json)
                else:
                    logger.warning(
                        "No matching file for {file_json} to {file_py}",
                        file_json=file_json,
                        file_py=file_py,
                    )

            # search py file after
            for file_py in directory.glob("*.py"):
                if file_py.name.startswith("_") or file_py in self.entry_files:
                    continue

                try:
                    self._register(*extract_entry_from_py(file_py))
                except Exception as e:
                    logger.warning(
                        "Failed to register catalog entry from {file_py}: {e}",
                        file_py=file_py,
                        e=e,
                    )

        self._compute_tree()

    def _register(self, json_content, py_file, module=None):
        if py_file in self.entry_files:
            return

        entry = CatalogEntry(json_content, py_file, module)
        self.entry_files.add(entry.file)
        self.entries[entry.name] = entry
        logger.debug("Registering catalog entry from {}", entry.file)

    def _compute_tree(self):
        self.root.children = []
        tree_index = {}
        for entry in self.entries.values():
            item = entry.to_item(self.server, self.favorites)
            current_container = self.root
            current_path = []
            for path_token in entry.path:
                current_path.append(path_token)
                path_key = tuple(current_path)
                if path_key not in tree_index:
                    folder = data_model.CatalogFolder(self.server, title=path_token)
                    current_container.children.append(folder)
                    tree_index[path_key] = folder
                current_container = tree_index[path_key]
            current_container.children.append(item)

        self.root.update_count()
