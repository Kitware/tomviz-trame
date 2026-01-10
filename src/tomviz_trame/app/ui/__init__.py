from trame.app.dev import reload as dev_reload

from . import (
    drawer_info,
    drawer_pipeline,
    drawer_properties,
    open_data,
    render_view,
    settings,
    toolbar,
    utils,
)
from .drawer_info import DataInformationSection
from .drawer_pipeline import PipelineSection
from .drawer_properties import PropertiesSections
from .dynamic import initialize_dynamic_ui
from .open_data import FileLoader
from .render_view import RenderWindow
from .settings import SettingsDialog
from .toolbar import Toolbar
from .utils import toolbar_btn


def reload(m=None):
    """Reload ui modules to help with the --hot-reload option of trame"""
    dev_reload(
        drawer_info,
        drawer_pipeline,
        drawer_properties,
        open_data,
        render_view,
        settings,
        toolbar,
        utils,
    )

    if m:
        m.__loader__.exec_module(m)


__all__ = [
    "DataInformationSection",
    "FileLoader",
    "PipelineSection",
    "PropertiesSections",
    "RenderWindow",
    "SettingsDialog",
    "Toolbar",
    "initialize_dynamic_ui",
    "toolbar_btn",
]
