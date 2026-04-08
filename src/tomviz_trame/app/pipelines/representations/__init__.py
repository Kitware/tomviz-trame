import importlib.util
from pathlib import Path

REPRESENTATIONS_PATH = Path(__file__).parent


def load_representations():
    for module_path in REPRESENTATIONS_PATH.glob("*.py"):
        if module_path.stem[0] == "_":
            continue
        name = module_path.stem
        spec = importlib.util.spec_from_file_location(name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
