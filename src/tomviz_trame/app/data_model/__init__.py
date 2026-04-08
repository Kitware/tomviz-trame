from __future__ import annotations

from trame.app.dataclass import get_instance

from .color_presets import ColorMaps, ColorPreset
from .pipeline import ColorOpacity, Pipeline, SourceProxy, create_default_color_opacity
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
    "create_default_color_opacity",
    "get_instance",
]
