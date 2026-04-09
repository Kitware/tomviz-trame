import importlib
import importlib.util
import json
from pathlib import Path

from loguru import logger
from trame.app import TrameComponent
from trame.decorators import controller

from tomviz_trame.app import data_model

DEFAULT_CONFIG = Path.home() / ".tomviz" / "operators.json"

DEFAULT_MODULES = [
    "tomviz.operators.builtin",
]
DEFAULT_DIRECTORIES = [
    (Path.home() / ".tomviz" / "operators"),
]


def module_to_path(module_name):
    loaded_module = importlib.import_module(module_name)
    module_path = Path(loaded_module.__file__)
    if module_path.is_file():
        return str(module_path.parent.resolve())
    return str(module_path.resolve())


def extract_operator_from_py(module_path: Path):
    name = module_path.name
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.JSON, module_path, module


class OperatorEntry:
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

    def to_operator_node(self, server, favs):
        return data_model.OperatorNode(
            server,
            title=self.label,
            name=self.name,
            tags=self.tags,
            icon=self.icon,
            favorite=self.name in favs,
        )


class Operators(TrameComponent):
    def __init__(self, server=None, config_file=None, read_only=False):
        super().__init__(server)
        self.read_only = read_only
        self.favorites = set()
        self.directories = set()
        self.modules = set()
        self.operators = {}
        self.operator_py_files = set()
        self.config_file = Path(config_file or DEFAULT_CONFIG)
        self.root_node = data_model.OperatorTreeNode(self.server)

        if not self.config_file.exists():
            if config_file is None:
                self.add_defaults()
                self.save()
            else:
                msg = f"Invalid path to config: {config_file}"
                raise ValueError(msg)

        config = json.loads(self.config_file.read_text())
        self.directories.update(config.get("directories", []))
        self.modules.update(config.get("modules", []))
        self.favorites.update(config.get("favorites", []))
        self.state.operator_favorite_count = len(self.favorites)
        self.update()

    @controller.set("update_favorite_operator")
    def update_favorite_operator(self, name, favorite):
        if favorite:
            self.favorites.add(name)
        else:
            self.favorites.discard(name)

        with self.state as s:
            s.operator_favorite_count = len(self.favorites)

        self.save()

    def add_defaults(self):
        for m in DEFAULT_MODULES:
            self.add_module(m)
        for directory in DEFAULT_DIRECTORIES:
            self.add_directory(directory)

    def clear(self):
        self.directories.clear()
        self.modules.clear()

    def add_directory(self, operators_dir: str | Path):
        self.directories.add(str(Path(operators_dir).resolve()))

    def remove_directory(self, operators_dir: str | Path):
        self.directories.discard(str(Path(operators_dir).resolve()))

    def add_module(self, operators_module: str):
        self.modules.add(operators_module)

    def remove_module(self, operators_module: str):
        self.modules.discard(operators_module)

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
        self.operators.clear()
        all_directories = map(
            Path, [*self.directories, *map(module_to_path, self.modules)]
        )
        for directory in all_directories:
            if not directory.exists():
                continue

            # search json first
            for file_json in directory.glob("*.json"):
                file_py = file_json.with_suffix(".py")
                if file_py.exists():
                    try:
                        json_content = json.loads(file_json.read_text())
                        self._register_operator(json_content, file_py)
                    except json.decoder.JSONDecodeError:
                        self.operator_py_files.add(file_py)
                        logger.warning("Invalid operator {}", file_json)
                else:
                    logger.warning(
                        "No matching file for {file_json} to {file_py}",
                        file_json=file_json,
                        file_py=file_py,
                    )

            # search py file after
            for file_py in directory.glob("*.py"):
                if file_py.name.startswith("_") or file_py in self.operator_py_files:
                    continue

                try:
                    self._register_operator(*extract_operator_from_py(file_py))
                except Exception as e:
                    logger.warning(
                        "Failed to register operator from {file_py}: {e}",
                        file_py=file_py,
                        e=e,
                    )

        self._compute_tree()

    def _register_operator(self, json_content, py_file, module=None):
        if py_file in self.operator_py_files:
            return

        entry = OperatorEntry(json_content, py_file, module)
        self.operator_py_files.add(entry.file)
        self.operators[entry.name] = entry
        logger.debug("Registering operator from {}", entry.file)

    def _compute_tree(self):
        self.root_node.children = []
        tree_index = {}
        for entry in self.operators.values():
            path = entry.path
            operator_node = entry.to_operator_node(self.server, self.favorites)
            current_container = self.root_node
            current_path = []
            for path_token in path:
                current_path.append(path_token)
                path_key = tuple(current_path)
                if path_key not in tree_index:
                    new_node = data_model.OperatorTreeNode(
                        self.server, title=path_token
                    )
                    current_container.children.append(new_node)
                    tree_index[path_key] = new_node
                current_container = tree_index[path_key]
            current_container.children.append(operator_node)

        self.root_node.update_count()

    def get_operator(self, name):
        """
        https://github.com/OpenChemistry/tomviz/blob/7d43eca7189d8df96e00c389de15b7d39cc674ed/tests/python/utils.py#L15
        find_transform:
            https://github.com/OpenChemistry/tomviz/blob/7d43eca7189d8df96e00c389de15b7d39cc674ed/tomviz/python/tomviz/_internal.py
        """
