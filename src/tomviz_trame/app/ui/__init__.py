from trame.app.dev import reload as dev_reload

from . import (
    open_data,
    render_view,
    settings,
    utils,
)
from .open_data import FileLoader
from .render_view import RenderWindow
from .settings import SettingsDialog
from .utils import toolbar_btn


def reload(m=None):
    """Reload ui modules to help with the --hot-reload option of trame"""
    dev_reload(open_data, render_view, settings, utils)

    if m:
        m.__loader__.exec_module(m)


__all__ = [
    "FileLoader",
    "RenderWindow",
    "SettingsDialog",
    "toolbar_btn",
]
