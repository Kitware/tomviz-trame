from pathlib import Path

from loguru import logger
from paraview import simple


def load_plugins(ns=None):
    for file in Path(__file__).parent.glob("*.py"):
        if file.name.startswith("_"):
            continue
        logger.debug("Loading plugin: {}", file.resolve())
        simple.LoadPlugin(str(file.resolve()), ns=ns)
