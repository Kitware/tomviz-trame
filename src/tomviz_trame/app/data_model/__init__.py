from trame.app.dataclass import get_instance

from .color_opacity import ColorOpacity, create_default_coloropacity
from .color_presets import ColorMaps, ColorPreset
from .pipeline import Pipeline, SourceProxy
from .representations import (
    REPRESENTATIONS,
    OutlineProperties,
    SliceProperties,
    VolumeProperties,
)
from .view import WindowInternalState

__all__ = [
    "REPRESENTATIONS",
    "ColorMaps",
    "ColorOpacity",
    "ColorPreset",
    "OutlineProperties",
    "Pipeline",
    "SliceProperties",
    "SourceProxy",
    "VolumeProperties",
    "WindowInternalState",
    "create_default_coloropacity",
    "get_instance",
]
