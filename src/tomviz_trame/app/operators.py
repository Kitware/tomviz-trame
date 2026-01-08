import json
from pathlib import Path

from trame.app import TrameComponent

DEFAULT_CONFIG = Path.home() / ".tomviz" / "operators.json"

DEFAULT_MODULES = [
    "tomviz_trame.operators",
]
DEFAULT_DIRECTORIES = [
    (Path.home() / ".tomviz" / "operators"),
]


class Operators(TrameComponent):
    def __init__(self, server=None, config_file=None, read_only=False):
        super().__init__(server)
        self.read_only = read_only
        self.directories = set()
        self.modules = set()
        self.config_file = Path(config_file or DEFAULT_CONFIG)

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
        self.update()

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
        self.directories.add(operators_module)

    def remove_module(self, operators_module: str):
        self.directories.discard(operators_module)

    def save(self):
        if self.read_only:
            return

        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(
            json.dumps(
                {
                    "directories": list(self.directories),
                    "modules": list(self.modules),
                },
                indent=2,
            )
        )

    def update(self): ...

    def get_operator(self, name): ...
